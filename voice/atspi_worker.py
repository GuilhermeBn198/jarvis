"""GI worker, kept out of the voice process to bound stalled applications."""
import json
import sys
from linux_context import object_id, parse_window_id, flatten_accessibility, walk_objects


def execute(operation,args):
    import gi
    gi.require_version('Atspi','2.0')
    from gi.repository import Atspi
    Atspi.set_timeout(1500,3000)
    desktop=Atspi.get_desktop(0)
    if desktop is None:raise RuntimeError('registro AT-SPI indisponivel')
    windows=[]
    for index in range(min(desktop.get_child_count(),200)):
        app=desktop.get_child_at_index(index)
        if app is None:continue
        for child in range(min(app.get_child_count(),200)):
            frame=app.get_child_at_index(child)
            if frame is not None:windows.append(frame)
    if operation=='windows':
        return {'status':'ok','windows':[{'id':object_id(node),'title':node.get_name(),
                'pid':node.get_process_id(),'process':node.get_application().get_name()} for node in windows]}
    target=args.get('window','')
    if not isinstance(target,str) or not target:raise ValueError('window explicita necessaria')
    if target.startswith('atspi:'):
        parse_window_id(target)
        candidates=[node for node in windows if object_id(node)==target]
    else:candidates=[node for node in windows if target.lower() in node.get_name().lower()]
    if len(candidates)!=1:return {'status':'ambiguous' if candidates else 'unavailable','detail':'alvo ambiguo ou indisponivel; use ID de desktop_list'}
    window=candidates[0]
    if operation=='tree':return {'status':'ok','nodes':flatten_accessibility(window,args.get('max_nodes',200))}
    if operation!='act_type':return {'status':'unsupported','detail':'AT-SPI nao oferece atalho arbitrario em background; foco preservado'}
    text=args.get('text')
    if not isinstance(text,str) or len(text)>100000 or '\x00' in text:raise ValueError('texto invalido')
    editors=[]
    for node,_ in walk_objects(window,200,12):
        try:
            if 'password' in node.get_role_name().lower():continue
            editable=node.get_editable_text_iface()
            if editable is not None and node.get_state_set().contains(Atspi.StateType.EDITABLE):
                if not args.get('control') or object_id(node)==args['control']:editors.append(node)
        except Exception:continue
    if len(editors)!=1:return {'status':'ambiguous' if editors else 'unsupported','detail':'selecione control editavel por ID de desktop_tree; nenhuma entrada enviada'}
    def focus_snapshot():
        focused=[]
        for frame in windows:
            for node,_ in walk_objects(frame,200,12):
                if node.get_state_set().contains(Atspi.StateType.FOCUSED):focused.append(object_id(node))
        return sorted(focused)
    before=focus_snapshot()
    if not before:return {'status':'unsupported','detail':'nao foi possivel verificar foco; background recusado'}
    editor=editors[0]
    iface=editor.get_text_iface()
    old=Atspi.Text.get_text(iface,0,-1)
    desired=old+text if args.get('append') else text
    accepted=editor.get_editable_text_iface().set_text_contents(desired)
    after=focus_snapshot()
    actual=Atspi.Text.get_text(iface,0,-1)
    if before!=after:return {'status':'unconfirmed','detail':'aplicativo alterou o foco ao atender AT-SPI; nao repetir automaticamente'}
    if not accepted or actual!=desired:return {'status':'unconfirmed','detail':'texto nao foi confirmado pelo aplicativo'}
    return {'status':'ok','detail':'texto verificado via AT-SPI; foco preservado'}


if __name__=='__main__':
    try:
        data=json.loads(sys.stdin.buffer.read(512*1024))
        result=execute(data.get('operation',''),data.get('args',{}))
    except Exception as exc:result={'status':'unavailable','detail':f'AT-SPI: {exc}'}
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['status'] in ('ok','unconfirmed') else 1)
