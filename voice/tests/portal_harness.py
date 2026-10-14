"""Private D-Bus integration harness; never connects to the user's portal."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from portal import PortalClient, PortalError, DESTINATION, REQUEST_INTERFACE


async def main(scenario):
    bus = await MessageBus().connect()
    closed = []
    rogue = await MessageBus().connect()
    if scenario != 'missing':
        await bus.request_name(DESTINATION)

    def handle(message):
        if message.message_type != MessageType.METHOD_CALL:
            return
        if message.interface == REQUEST_INTERFACE and message.member == 'Close':
            closed.append(message.path)
            return Message.new_method_return(message)
        if message.interface != 'org.freedesktop.portal.Screenshot' or message.member != 'Screenshot':
            return
        token = message.body[1]['handle_token'].value
        sender = message.sender.lstrip(':').replace('.', '_')
        path = f'/org/freedesktop/portal/desktop/request/{sender}/{token}'
        if scenario == 'forged':
            rogue.send(Message.new_signal(path, REQUEST_INTERFACE, 'Response', 'ua{sv}',
                       [0, {'uri': Variant('s', 'file:///forged.png')}]))
        if scenario != 'timeout':
            code = {'cancelled': 1, 'denied': 2}.get(scenario, 0)
            # Emit before method reply to exercise the response race.
            bus.send(Message.new_signal(path, REQUEST_INTERFACE, 'Response', 'ua{sv}',
                     [code, {'uri': Variant('s', 'file:///correct.png')}]))
        return Message.new_method_return(message, 'o', [path])

    bus.add_message_handler(handle)
    try:
        result = await PortalClient().request_async('org.freedesktop.portal.Screenshot',
                                                   'Screenshot', ('', {}), 0.3)
        assert scenario in ('success', 'forged'), (scenario, result)
        assert result == {'uri': 'file:///correct.png'}, result
    except PortalError as exc:
        assert exc.code == {'missing': 'unavailable'}.get(scenario, scenario), (scenario, exc.code)
    if scenario != 'missing':
        assert len(closed) == 1, closed
    bus.disconnect()
    rogue.disconnect()


asyncio.run(main(sys.argv[1]))
