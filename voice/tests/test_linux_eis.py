import pytest

from linux_eis import EISPointer, evdev_button


@pytest.mark.parametrize(
    ('name', 'code'),
    [('left', 0x110), ('right', 0x111), ('middle', 0x112)],
)
def test_evdev_button_codes(name, code):
    assert evdev_button(name) == code


def test_eis_click_waits_for_pointer_and_button_device_and_frames_release():
    class Device:
        capabilities = (2, 32)  # POINTER_ABSOLUTE and BUTTON

        def __init__(self):
            self.events = []

        def region_at(self, x, y):
            if (x, y) != (1120.0, 580.0):
                return None
            return type('Region', (), {
                'convert_point': lambda self, px, py: (px - 1000, py - 500),
            })()

        def start_emulating(self):
            self.events.append(('start',))
            return self

        def pointer_motion_absolute(self, x, y):
            self.events.append(('motion', x, y))
            return self

        def button(self, code, pressed):
            self.events.append(('button', code, pressed))
            return self

        def frame(self):
            self.events.append(('frame',))
            return self

        def stop_emulating(self):
            self.events.append(('stop',))
            return self

    device = Device()
    seat = type('Seat', (), {'bind': lambda self, capabilities: None})()
    event = type('Event', (), {'event_type': 3, 'seat': seat, 'device': None})()
    resumed = type('Event', (), {'event_type': 8, 'seat': None, 'device': device})()

    class Sender:
        fd = 0
        events = iter(())

        @classmethod
        def create_for_fd(cls, fd, name=None):
            return cls()

        def dispatch(self):
            self.events = iter((event, resumed))

    class Session:
        eis_fd = 42

        @classmethod
        def negotiate(cls, **kwargs):
            return cls()

        def close(self):
            pass

    class EI:
        class EventType:
            SEAT_ADDED = 3
            SEAT_REMOVED = 4
            DEVICE_REMOVED = 6
            DEVICE_PAUSED = 7
            DEVICE_RESUMED = 8
            DISCONNECT = 2

        class DeviceCapability:
            POINTER_ABSOLUTE = 2
            BUTTON = 32

        @staticmethod
        def is_available():
            return True

    EI.Sender = Sender

    class Portal:
        class DeviceType:
            POINTER = 2

        RemoteDesktopSession = Session

        @staticmethod
        def is_available():
            return True

    pointer = EISPointer(ei_api=EI, portal_api=Portal, select_fn=lambda *args: ([0], [], []))

    result = pointer.click({'x': 1120, 'y': 580, 'button': 'right'})

    assert result['status'] == 'unconfirmed'
    assert device.events == [
        ('start',), ('motion', 120.0, 80.0),
        ('button', 0x111, True), ('frame',),
        ('button', 0x111, False), ('frame',), ('stop',),
    ]


def test_eis_click_does_not_send_when_coordinate_is_outside_regions():
    class Device:
        capabilities = (2, 32)

        def region_at(self, _x, _y):
            return None

    class EI:
        class DeviceCapability:
            POINTER_ABSOLUTE = 2
            BUTTON = 32

    pointer = EISPointer(ei_api=EI, portal_api=object())
    assert pointer._click_device(Device(), {'x': 3, 'y': 4, 'button': 'left'})['status'] == 'error'


def test_eis_click_refuses_input_after_portal_pauses_device():
    class Device:
        capabilities = (2, 32)

        def __init__(self): self.events=[]
        def region_at(self, _x, _y): return object()
        def start_emulating(self): self.events.append('start')
        def pointer_motion_absolute(self, *_): self.events.append('motion')
        def button(self, *_): self.events.append('button')
        def frame(self): self.events.append('frame')
        def stop_emulating(self): self.events.append('stop')

    device=Device()
    paused=type('Event',(),{'event_type':7,'device':device})()

    class Sender:
        fd=9
        events=()
        def dispatch(self): self.events=(paused,)

    class EI:
        class EventType:
            DEVICE_PAUSED=7
        class DeviceCapability:
            POINTER_ABSOLUTE=2
            BUTTON=32
        @staticmethod
        def is_available(): return True

    class Portal:
        @staticmethod
        def is_available(): return True
        class DeviceType:
            POINTER=2

    pointer=EISPointer(ei_api=EI,portal_api=Portal,
                       select_fn=lambda *args: ([9],[],[]))
    pointer._sender=Sender()
    pointer._device=device
    pointer._device_active=True

    result=pointer.click({'x':10,'y':20})

    assert result['status']=='denied'
    assert device.events==[]


def test_missing_native_eis_requests_legacy_fallback():
    class EI:
        @staticmethod
        def is_available():
            return False

    pointer = EISPointer(ei_api=EI, portal_api=object())
    assert pointer.click({'x': 1, 'y': 2})['status'] == 'unsupported'


def test_old_libei_without_region_api_requests_legacy_fallback():
    class LibraryNotFoundError(Exception):
        pass

    class EI:
        class DeviceCapability:
            POINTER_ABSOLUTE = 2
            BUTTON = 32

        @staticmethod
        def is_available():
            return True

    EI.LibraryNotFoundError = LibraryNotFoundError

    class Device:
        capabilities = (2, 32)

        def region_at(self, _x, _y):
            raise LibraryNotFoundError('ei_device_get_region_at missing')

    class Portal:
        @staticmethod
        def is_available():
            return True

    pointer = EISPointer(ei_api=EI, portal_api=Portal,
                         select_fn=lambda *args: ([], [], []))
    pointer._sender = type('Sender', (), {'fd': 0})()
    pointer._device = Device()
    pointer._device_active = True
    assert pointer.click({'x': 1, 'y': 2})['status'] == 'unsupported'


def test_eis_click_refuses_device_paused_in_initial_resume_batch():
    class Device:
        capabilities = (2, 32)

        def __init__(self): self.events=[]
        def region_at(self, _x, _y): return object()
        def start_emulating(self): self.events.append('start')
        def pointer_motion_absolute(self, *_): self.events.append('motion')
        def button(self, *_): self.events.append('button')
        def frame(self): self.events.append('frame')
        def stop_emulating(self): self.events.append('stop')

    device=Device()
    resumed=type('Event',(),{'event_type':8,'device':device,'seat':None})()
    paused=type('Event',(),{'event_type':7,'device':device,'seat':None})()

    class Sender:
        fd=9
        events=()
        def dispatch(self): self.events=(resumed,paused)
        @classmethod
        def create_for_fd(cls, _fd, name=None): return cls()

    class Session:
        eis_fd=10
        @classmethod
        def negotiate(cls, **_kwargs): return cls()
        def close(self): pass

    class EI:
        class EventType:
            SEAT_ADDED=3
            SEAT_REMOVED=4
            DEVICE_REMOVED=6
            DEVICE_PAUSED=7
            DEVICE_RESUMED=8
            DISCONNECT=2
        class DeviceCapability:
            POINTER_ABSOLUTE=2
            BUTTON=32
        @staticmethod
        def is_available(): return True

    EI.Sender=Sender

    class Portal:
        class DeviceType:
            POINTER=2
        RemoteDesktopSession=Session
        @staticmethod
        def is_available(): return True

    readiness=iter((([9],[],[]),([],[],[])))
    pointer=EISPointer(ei_api=EI,portal_api=Portal,select_fn=lambda *_: next(readiness))

    result=pointer.click({'x':10,'y':20})

    assert result['status']=='denied'
    assert device.events==[]
