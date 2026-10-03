"""Pure, sanitized native HR inventory projection for conditional source inference."""
from analysis.activity_dfa import DFAError, GARMIN_ECG, SOURCE_VERSION, digest, sensor_evidence

SOURCE_RULE_VERSION = 'dfa-native-ecg-metadata-v1'
METADATA_PROJECTION_VERSION = 'rr-native-source-metadata-v2'
FROZEN_NUMERICAL_DIGEST = 'f36cf405cbf84aef9d04e6e52aa1600662ce0254de1b230d7372ff035ebede11'
AUTO_SDR_ID = 'sdr-activity-dfa-alpha1-v2'


def _hr_relevant(values:dict) -> bool:
    manufacturer,product=values.get('manufacturer'),values.get('product')
    name=str(values.get('product_name') or values.get('name') or '').strip(' \t\n\r\v\f').lower()
    transport,device_class=values.get('source_type'),values.get('device_type')
    return (manufacturer==1 and product in GARMIN_ECG or manufacturer==123 and name in ('h10','polar h10')
        or (transport,device_class) in ((1,120),(3,1),(5,10))
        or transport in (1,3) and device_class is None or device_class==120 and transport is None)


def require_native_integrity(messages:list[dict],recording_ref:dict|None=None) -> dict:
    """Owner clarification permits unresolved evidence, never native conflicts."""
    inventory=source_inventory(messages,recording_ref or {})
    if inventory['outcome']=='source_ineligible':
        raise DFAError('source_contradiction')
    return inventory


def source_inventory(messages: list[dict], recording_ref: dict) -> dict:
    """Inspect every external HR descriptor; no serial/address is projected."""
    try:
        sensor_evidence(messages)  # existing positive handle identity contradictions
    except DFAError:
        return {'outcome':'source_ineligible','reason':'source_contradiction','candidates':[]}
    handles, unresolved = {}, False
    # Merge every partial native descriptor before deciding relevance. A name-
    # only or product-only row can contradict or complete a later HR handle.
    for entry in messages:
        if entry['message'] != 23:
            continue
        values = entry['values']
        index=values.get('device_index')
        if not isinstance(index,int) or isinstance(index,bool):
            index=('missing',entry['frame'])
        descriptor = handles.setdefault(index, {'facts':{},'conflicts':set(),'hr_relevant':False})
        descriptor['hr_relevant'] |= _hr_relevant(values)
        name=str(values.get('product_name') or '').strip(' \t\n\r\v\f').lower()
        if name in ('h10','polar h10'):
            name='h10'
        for key,value in [('manufacturer',values.get('manufacturer')),('product',values.get('product')),
                ('name',name or None),('source_type',values.get('source_type')),('device_type',values.get('device_type'))]:
            if value is not None:
                facts=descriptor['facts'].setdefault(key,set());facts.add(value)
                if len(facts)>1:
                    descriptor['conflicts'].add(key)
                descriptor[key]=value
    candidates, rules = [], set()
    inventory = []
    for index, descriptor in sorted(handles.items(),key=lambda item:str(item[0])):
        facts=descriptor['facts'];row={key:value for key,value in descriptor.items() if key not in ('facts','conflicts','hr_relevant')}
        manufacturer, product, name = row.get('manufacturer'), row.get('product'), row.get('name')
        label = GARMIN_ECG.get(product) if manufacturer == 1 else 'Polar H10' if manufacturer == 123 and name == 'h10' else None
        rule = digest([SOURCE_VERSION,manufacturer,'h10' if manufacturer == 123 else product]) if label else None
        pair = (row.get('source_type'),row.get('device_type'))
        ref = digest([recording_ref,METADATA_PROJECTION_VERSION,index])[:32]
        # Bind all native handle facts, including descriptors that are unrelated
        # to HR. No serial, address or raw native payload enters this projection.
        inventory.append({'candidate_ref':ref,**{key:sorted(values) for key,values in facts.items()}})
        # Earlier native HR evidence stays relevant even when the last scalar
        # class/transport describes a different or unknown device category.
        relevant = descriptor['hr_relevant'] or _hr_relevant(row)
        if not relevant:
            continue
        if descriptor['conflicts'] & {'manufacturer','product','name'}:
            return {'outcome':'source_ineligible','reason':'source_contradiction','candidates':[]}
        if descriptor['conflicts'] or not label or pair not in ((1,120),(3,1)) or not isinstance(index,int):
            unresolved = True
        if label:
            candidates.append({'sensor_ref':ref,'label':label,'transport':'ANT+' if pair == (1,120) else 'BLE' if pair == (3,1) else None,'rule_fingerprint':rule})
            rules.add(rule)
    if len(rules) != 1 or not candidates:
        unresolved = True
    evidence = digest([recording_ref,METADATA_PROJECTION_VERSION,SOURCE_RULE_VERSION,inventory])
    return {'outcome':'source_unresolved' if unresolved else 'eligible_metadata_inferred',
            'reason':'source_unresolved' if unresolved else None,'source_evidence_digest':evidence,
            'source_rule_version':SOURCE_RULE_VERSION,'metadata_projection_version':METADATA_PROJECTION_VERSION,
            'candidates':candidates}
