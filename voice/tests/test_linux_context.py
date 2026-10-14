import pytest
from linux_context import flatten_accessibility, window_id, parse_window_id, processes


class Node:
    def __init__(self,name,children=()):
        self.name=name;self.children=children;self.path='/'+name;self.app=type('App',(),{'bus_name':':1.20'})()
    def get_name(self):return self.name
    def get_role_name(self):return 'test'
    def get_child_count(self):return len(self.children)
    def get_child_at_index(self,i):return self.children[i]


def test_tree_bounds_and_cycle_are_enforced():
    root=Node('root');child=Node('child');root.children=[child];child.children=[root]
    rows=flatten_accessibility(root,max_nodes=20,max_depth=10)
    assert len(rows)==2 and [row['name'] for row in rows]==['root','child']
    root.children=[Node(str(i)) for i in range(10)]
    assert len(flatten_accessibility(root,max_nodes=3,max_depth=10))==3
    assert len(flatten_accessibility(root,max_nodes=30,max_depth=0))==1


def test_opaque_ids_roundtrip_and_reject_foreign_values():
    identifier=window_id(':1.20','/org/a11y/atspi/accessible/12')
    assert parse_window_id(identifier)==(':1.20','/org/a11y/atspi/accessible/12')
    for value in ('12','atspi:bad','atspi:','hwnd:12'):
        with pytest.raises(ValueError):parse_window_id(value)


def test_process_filter_is_literal():
    assert processes('not-a-process; echo hacked')=='(nenhum processo)'


def test_stalled_accessibility_worker_is_bounded(tmp_path,monkeypatch):
    import time
    import os
    from linux_context import accessibility_request,ContextError
    worker=tmp_path/'stalled-python'
    worker.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(2)\n')
    worker.chmod(0o700)
    monkeypatch.setenv('JARVIS_ACCESSIBILITY_PYTHON',str(worker))
    monkeypatch.setenv('DISPLAY',':test')
    started=time.monotonic()
    with pytest.raises(ContextError,match='timeout'):
        accessibility_request('windows',{},timeout_s=.05)
    assert time.monotonic()-started<1
