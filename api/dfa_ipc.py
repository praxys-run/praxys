"""Strict bounded private IPC schemas; no database, credentials or I/O."""
import json
import math
import re


class IPCInvalid(ValueError):
    pass


def loads(payload: bytes):
    def pairs(entries):
        result={}
        for key,value in entries:
            if key in result: raise IPCInvalid('duplicate_ipc_field')
            result[key]=value
        return result
    return json.loads(payload,object_pairs_hook=pairs,parse_constant=lambda value: (_ for _ in ()).throw(IPCInvalid('nonfinite_ipc')))


def binding(value):
    if (not isinstance(value,dict) or set(value)!={'epoch','generation','input'}
            or type(value['generation']) is not int or value['generation']<1
            or not isinstance(value['epoch'],str) or not value['epoch'].isdigit()
            or not isinstance(value['input'],str) or not re.fullmatch('[0-9a-f]{64}',value['input'])):
        raise IPCInvalid('ipc_binding_invalid')


def result(value,phase):
    if not isinstance(value,dict): raise IPCInvalid('ipc_result_type')
    if phase=='prepare':
        expected={'sensors','evidence_digest','statement_version','rr_count','frame_count','time_alignment'}
        if set(value)!=expected or not isinstance(value['sensors'],list): raise IPCInvalid('ipc_preparation_schema')
        if any(type(value[key]) is not int or value[key]<0 for key in ('rr_count','frame_count')):
            raise IPCInvalid('ipc_preparation_count')
        return
    expected={'method_version','source_assurance','time_alignment','availability','summary','navigation','windows'}
    if set(value)!=expected or not isinstance(value['windows'],list) or len(value['windows'])>34560:
        raise IPCInvalid('ipc_result_schema')
    summary=value['summary']
    if not isinstance(summary,dict) or any(type(summary.get(key)) is not int or summary[key]<0
        for key in ('scheduled_windows','valid_windows','short_blocks')):
        raise IPCInvalid('ipc_summary_schema')
    if summary['scheduled_windows']!=len(value['windows']) or summary['valid_windows']>summary['scheduled_windows']:
        raise IPCInvalid('ipc_window_count')
    for index,window in enumerate(value['windows']):
        if not isinstance(window,dict) or type(window.get('index')) is not int or window['index']!=index:
            raise IPCInvalid('ipc_window_index')
        for field in ('start_ms','end_ms','beat_count','coverage_ms','block'):
            if type(window.get(field)) is not int or window[field]<0: raise IPCInvalid('ipc_window_integer')
        if window['end_ms']-window['start_ms']!=120000: raise IPCInvalid('ipc_window_duration')
        for field in ('alpha1','hr_bpm','r2'):
            number=window.get(field)
            if number is not None and (type(number) not in (int,float) or not math.isfinite(number)):
                raise IPCInvalid('ipc_window_number')
        for field in ('reasons','flags'):
            if not isinstance(window.get(field),list) or any(not isinstance(item,str) or len(item)>80 for item in window[field]):
                raise IPCInvalid('ipc_reason_schema')
