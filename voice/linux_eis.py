"""Optional XDG RemoteDesktop input through the EIS/libei protocol."""
from __future__ import annotations

import select
import threading
import time

UNAVAILABLE = {'status': 'unsupported', 'detail': 'libei/EIS indisponivel; usando RemoteDesktop legado'}
UNCONFIRMED = {'status': 'unconfirmed', 'detail': 'clique enviado por EIS; aplicativo nao confirmou o resultado'}
BUTTONS = {'left': 0x110, 'right': 0x111, 'middle': 0x112}


def evdev_button(button: str = 'left') -> int:
    try:
        return BUTTONS[button]
    except KeyError as exc:
        raise ValueError('button invalido') from exc


class EISPointer:
    """Lazily hold one consented EIS pointer session for click requests."""

    def __init__(self, *, ei_api=None, portal_api=None, select_fn=None, timeout=60):
        self._ei_api = ei_api
        self._portal_api = portal_api
        self._select = select_fn or select.select
        self._timeout = timeout
        self._session = None
        self._sender = None
        self._device = None
        self._device_active = False
        self._lock = threading.RLock()

    def _apis(self):
        if self._ei_api is None or self._portal_api is None:
            try:
                from libei import ei, portal
            except ImportError:
                return None, None
            self._ei_api = ei
            self._portal_api = portal
        ei, portal = self._ei_api, self._portal_api
        if not ei.is_available() or not portal.is_available():
            return None, None
        return ei, portal

    def _click_device(self, device, args):
        caps = set(device.capabilities)
        required = (self._ei_api.DeviceCapability.POINTER_ABSOLUTE,
                    self._ei_api.DeviceCapability.BUTTON)
        if not all(cap in caps for cap in required):
            self.close()
            return {'status': 'unsupported', 'detail': 'EIS nao forneceu dispositivo de ponteiro absoluto'}
        x, y = float(args['x']), float(args['y'])
        region = device.region_at(x, y)
        if region is None:
            return {'status': 'error', 'detail': 'coordenadas fora das regioes de entrada EIS'}
        position = region.convert_point(x, y)
        if position is None:
            return {'status': 'error', 'detail': 'coordenadas fora das regioes de entrada EIS'}
        x, y = position
        code = evdev_button(args.get('button', 'left'))
        device.start_emulating()
        pressed = False
        try:
            device.pointer_motion_absolute(x, y)
            pressed = True
            device.button(code, True)
            device.frame()
            device.button(code, False)
            device.frame()
            pressed = False
        finally:
            if pressed:
                try:
                    device.button(code, False)
                    device.frame()
                except Exception:
                    pass
            device.stop_emulating()
        return dict(UNCONFIRMED)

    def _ensure_device(self):
        if self._device is not None:
            return self._device
        ei, portal = self._apis()
        if ei is None:
            return None
        try:
            self._session = portal.RemoteDesktopSession.negotiate(
                devices=portal.DeviceType.POINTER, timeout=self._timeout)
            self._sender = ei.Sender.create_for_fd(self._session.eis_fd, name='Jarvis')
            deadline = time.monotonic() + self._timeout
            while self._device is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self._select([self._sender.fd], [], [], remaining)[0]:
                    raise TimeoutError('timeout aguardando dispositivo EIS')
                self._sender.dispatch()
                for event in self._sender.events:
                    if event.event_type == ei.EventType.SEAT_ADDED:
                        event.seat.bind((ei.DeviceCapability.POINTER_ABSOLUTE,
                                         ei.DeviceCapability.BUTTON))
                    elif event.event_type == ei.EventType.DEVICE_RESUMED:
                        caps = set(event.device.capabilities)
                        needed = (ei.DeviceCapability.POINTER_ABSOLUTE,
                                  ei.DeviceCapability.BUTTON)
                        if all(cap in caps for cap in needed):
                            self._device = event.device
                            self._device_active = True
                    elif (event.event_type == ei.EventType.DEVICE_PAUSED
                          and event.device is self._device):
                        self._device_active = False
                    elif event.event_type in (ei.EventType.DEVICE_REMOVED,
                                               ei.EventType.SEAT_REMOVED,
                                               ei.EventType.DISCONNECT):
                        self.close()
                        raise RuntimeError('dispositivo ou sessao EIS removido')
            return self._device
        except Exception:
            self.close()
            raise

    def _refresh_device(self, ei):
        if self._sender is None or self._device is None:
            return False
        if self._select([self._sender.fd], [], [], 0)[0]:
            self._sender.dispatch()
            event_types = ei.EventType
            for event in self._sender.events:
                if event.event_type == event_types.DEVICE_PAUSED:
                    self._device_active = False
                elif event.event_type == event_types.DEVICE_RESUMED:
                    caps = set(event.device.capabilities)
                    needed = (ei.DeviceCapability.POINTER_ABSOLUTE,
                              ei.DeviceCapability.BUTTON)
                    if all(cap in caps for cap in needed):
                        self._device = event.device
                        self._device_active = True
                elif event.event_type in (event_types.DEVICE_REMOVED,
                                           event_types.SEAT_REMOVED,
                                           event_types.DISCONNECT):
                    self.close()
                    return False
        return self._device_active

    def click(self, args: dict) -> dict:
        ei, portal = self._apis()
        if ei is None:
            return dict(UNAVAILABLE)
        with self._lock:
            try:
                device = self._ensure_device()
                if device is None:
                    return dict(UNAVAILABLE)
                if not self._refresh_device(ei):
                    return {'status': 'denied', 'detail': 'dispositivo EIS pausado ou revogado'}
                device = self._device
                return self._click_device(device, args)
            except getattr(portal, 'PortalVersionError', ()):
                self.close()
                return dict(UNAVAILABLE)
            except getattr(portal, 'PortalDeniedError', ()) as exc:
                self.close()
                return {'status': 'denied', 'detail': str(exc)}
            except getattr(portal, 'PortalTimeoutError', ()) as exc:
                self.close()
                return {'status': 'timeout', 'detail': str(exc)}
            except getattr(ei, 'LibraryNotFoundError', ()) as exc:
                self.close()
                return {'status': 'unsupported', 'detail': f'libei sem API EIS necessaria: {exc}'}
            except Exception as exc:
                self.close()
                return {'status': 'error', 'detail': f'falha no EIS: {exc}'}

    def close(self):
        with self._lock:
            self._device = None
            self._device_active = False
            self._sender = None
            session, self._session = self._session, None
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass
