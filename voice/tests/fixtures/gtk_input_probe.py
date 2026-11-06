import gi,json,sys,os
from pathlib import Path
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib,Gdk
window=Gtk.Window(title=f'Jarvis Linux input probe {os.getpid()}')
window.set_default_size(500,140)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
box.set_border_width(16)
entry=Gtk.Entry();entry.set_placeholder_text('Teste isolado de entrada do Jarvis')
button=Gtk.Button(label='Confirmar teste')
count=[0]
button.connect('clicked',lambda *_:count.__setitem__(0,count[0]+1))
box.pack_start(entry,True,True,0);box.pack_start(button,True,True,0)
window.add(box);window.connect('destroy',Gtk.main_quit)
window.show_all();entry.grab_focus();window.present()
sentinel=Gtk.Window(title='Jarvis focus sentinel')
sentinel.set_default_size(350,80)
focus_entry=Gtk.Entry();sentinel.add(focus_entry)
sentinel.show_all();focus_entry.grab_focus();sentinel.present()
path=Path(sys.argv[1])
def report():
    path.write_text(json.dumps({'active':window.is_active(),'text':entry.get_text(),'clicks':count[0],'display':Gdk.Display.get_default().get_name(),'sentinel_active':sentinel.is_active(),'sentinel_text':focus_entry.get_text()},ensure_ascii=False))
    return True
GLib.timeout_add(100,report)
Gtk.main()
