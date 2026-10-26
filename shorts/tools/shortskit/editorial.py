"""Reusable editorial evidence validator; does not fabricate taste, listening or semantic proof."""
def check_cut(cut):
    issues=[]
    bank={s['id']:s for s in cut.get('shot_bank',[])}
    if not bank:issues.append('shot bank missing')
    for id,s in bank.items():
        for k in ['source','in','out','action','quality_review','crop_review','role']:
            if k not in s:issues.append(id+': '+k+' missing')
        if s.get('out',0)<=s.get('in',0):issues.append(id+': invalid source span')
    events=cut.get('music_events',[])
    if cut.get('music_required'):
        if not events:issues.append('real musical events missing; BPM is insufficient')
        if not cut.get('exact_music_verified'):issues.append('exact track/version unverified')
        if cut.get('music_listened') is not True:issues.append('music not listened; computed onset is only a candidate')
    for e in events:
        if not all(k in e for k in ['t','kind','evidence']):issues.append('music event missing timestamp/kind/evidence')
    timeline=cut.get('timeline',[])
    for s in timeline:
        if s.get('shot') not in bank:issues.append('timeline references unknown shot')
        if s.get('effect') and not s.get('effect_role'):issues.append('effect without motivated role')
        if s.get('anchor') and not s.get('anchor_role'):issues.append('anchor lacks visual event role')
    roles={x.get('role') for x in timeline}
    if not {'opening','development','payoff','ending'}<=roles:issues.append('dramatic arc incomplete')
    if cut.get('motion_reviewed') is not True:issues.append('movement not reviewed')
    return {'ready':not issues,'issues':issues}
