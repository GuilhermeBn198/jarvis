"""XDG portal requests with response subscription installed before the call."""
import asyncio
import uuid
from tts import VoiceError

DESTINATION = 'org.freedesktop.portal.Desktop'
OBJECT = '/org/freedesktop/portal/desktop'
REQUEST_INTERFACE = 'org.freedesktop.portal.Request'


class PortalError(VoiceError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(detail)


def decode_response(code: int, values: dict) -> dict:
    if code != 0:
        status = {1: 'cancelled', 2: 'denied'}.get(code, 'error')
        raise PortalError(status, f'portal: {status}')
    return {key: getattr(value, 'value', value) for key, value in values.items()}


class PortalClient:
    def __init__(self, persistent: bool = False):
        self.persistent = persistent
        self.bus = None
        self.owner = None
        self.session_handlers = []

    async def close(self):
        if self.bus is not None:
            for handler in self.session_handlers:
                self.bus.remove_message_handler(handler)
            self.session_handlers.clear()
            self.bus.disconnect()
            self.bus = None

    async def call(self, interface: str, method: str, signature: str, body: list, path=None):
        from dbus_next import Message, MessageType
        if self.bus is None:
            raise PortalError("unavailable", "sessao de portal nao conectada")
        try:
            reply = await asyncio.wait_for(self.bus.call(Message(destination=self.owner,
                path=path or OBJECT, interface=interface, member=method,
                signature=signature, body=body)), 10)
        except (OSError, EOFError, asyncio.TimeoutError) as exc:
            raise PortalError("unavailable", f"conexao de portal perdida: {exc}") from exc
        if reply is None or reply.message_type == MessageType.ERROR:
            raise PortalError("denied", f"portal recusou {method}: {getattr(reply, 'error_name', None)}")
        return reply.body

    async def watch_session(self, session: str, callback):
        from dbus_next import Message, MessageType
        owner = self.owner
        def handle(message):
            if (message.message_type == MessageType.SIGNAL and message.sender == owner
                    and message.path == session and message.interface == "org.freedesktop.portal.Session"
                    and message.member == "Closed"):
                callback()
        self.bus.add_message_handler(handle)
        self.session_handlers.append(handle)
        rule = f"type='signal',sender='{owner}',path='{session}',interface='org.freedesktop.portal.Session',member='Closed'"
        reply = await asyncio.wait_for(self.bus.call(Message(destination='org.freedesktop.DBus',
            path='/org/freedesktop/DBus',interface='org.freedesktop.DBus',member='AddMatch',
            signature='s',body=[rule])),10)
        if reply.message_type == MessageType.ERROR:
            raise PortalError('unavailable','nao foi possivel acompanhar sessao do portal')

    def request(self, interface: str, method: str, args: tuple, timeout_s: float) -> dict:
        return asyncio.run(self.request_async(interface, method, args, timeout_s))

    async def request_async(self, interface: str, method: str, args: tuple, timeout_s: float) -> dict:
        try:
            from dbus_next import Message, MessageType, Variant
            from dbus_next.aio import MessageBus
            from dbus_next.errors import InvalidAddressError, DBusError
        except ImportError as exc:
            raise PortalError('unavailable', 'portal exige dbus-next no ambiente Python') from exc
        signatures = {'Screenshot': 'sa{sv}', 'CreateSession': 'a{sv}',
                      'SelectDevices': 'oa{sv}', 'SelectSources': 'oa{sv}', 'Start': 'osa{sv}'}
        if method not in signatures or not args or not isinstance(args[-1], dict):
            raise PortalError('error', f'metodo de portal nao suportado: {method}')
        bus = None
        request_path = None
        handle = None
        rule = None
        try:
            bus = self.bus or await asyncio.wait_for(MessageBus().connect(), timeout_s)
            if self.persistent:
                self.bus = bus
            owner_reply = await asyncio.wait_for(bus.call(Message(destination='org.freedesktop.DBus',
                path='/org/freedesktop/DBus', interface='org.freedesktop.DBus',
                member='GetNameOwner', signature='s', body=[DESTINATION])), timeout_s)
            if owner_reply.message_type == MessageType.ERROR:
                raise PortalError('unavailable', 'servico xdg-desktop-portal indisponivel')
            owner = owner_reply.body[0]
            self.owner = owner
            token = 'jarvis_' + uuid.uuid4().hex
            sender = bus.unique_name.lstrip(':').replace('.', '_')
            request_path = f'/org/freedesktop/portal/desktop/request/{sender}/{token}'
            response = asyncio.get_running_loop().create_future()

            def handle(message):
                if (message.message_type == MessageType.SIGNAL and message.sender == owner
                        and message.path == request_path and message.interface == REQUEST_INTERFACE
                        and message.member == 'Response' and message.signature == 'ua{sv}'):
                    if not response.done():
                        response.set_result(message.body)

            bus.add_message_handler(handle)
            rule = (f"type='signal',sender='{owner}',interface='{REQUEST_INTERFACE}',"
                    f"member='Response',path='{request_path}'")
            match_reply = await asyncio.wait_for(bus.call(Message(destination='org.freedesktop.DBus',
                path='/org/freedesktop/DBus', interface='org.freedesktop.DBus', member='AddMatch',
                signature='s', body=[rule])), timeout_s)
            if match_reply.message_type == MessageType.ERROR:
                raise PortalError('unavailable', 'nao foi possivel assinar Response do portal')
            options = dict(args[-1], handle_token=token)
            vardict = {}
            for key, value in options.items():
                if isinstance(value, Variant):
                    vardict[key] = value
                elif isinstance(value, bool):
                    vardict[key] = Variant('b', value)
                elif isinstance(value, int):
                    vardict[key] = Variant('u', value)
                elif isinstance(value, str):
                    vardict[key] = Variant('s', value)
                else:
                    raise PortalError('error', f'opcao de portal invalida: {key}')
            call_reply = await asyncio.wait_for(bus.call(Message(destination=owner, path=OBJECT,
                interface=interface, member=method, signature=signatures[method],
                body=[*args[:-1], vardict])), timeout_s)
            if call_reply.message_type == MessageType.ERROR:
                code = 'denied' if 'NotAllowed' in (call_reply.error_name or '') else 'unavailable'
                raise PortalError(code, f'portal {method}: {call_reply.error_name}')
            if call_reply.body != [request_path]:
                raise PortalError('error', 'portal retornou handle diferente do solicitado')
            code, values = await asyncio.wait_for(response, timeout_s)
            return decode_response(code, values)
        except asyncio.TimeoutError as exc:
            raise PortalError('timeout', 'timeout aguardando portal; nenhuma captura/acao confirmada') from exc
        except (OSError, EOFError, InvalidAddressError, DBusError) as exc:
            raise PortalError('unavailable', f'conexao de portal indisponivel: {exc}') from exc
        finally:
            if bus is not None:
                if request_path is not None:
                    try:
                        await asyncio.wait_for(bus.call(Message(destination=DESTINATION,
                            path=request_path, interface=REQUEST_INTERFACE, member='Close')), 1)
                    except Exception:
                        pass
                if handle is not None:
                    bus.remove_message_handler(handle)
                if self.persistent and rule is not None:
                    try:
                        await asyncio.wait_for(bus.call(Message(destination='org.freedesktop.DBus',
                            path='/org/freedesktop/DBus',interface='org.freedesktop.DBus',member='RemoveMatch',
                            signature='s',body=[rule])),1)
                    except Exception:
                        pass
                if not self.persistent:
                    bus.disconnect()
