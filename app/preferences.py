"""Bounded musical preferences translated to ACE-Step caption descriptions."""
GENDERS = {'auto': '', 'female': 'female lead vocals', 'male': 'male lead vocals'}
TONES = {'auto': '', 'clear': 'clear bright vocal timbre', 'warm': 'warm mellow vocal timbre',
         'husky': 'husky raspy vocal timbre', 'breathy': 'soft breathy vocal timbre',
         'powerful': 'powerful expressive vocal delivery'}
INSTRUMENTS = {'piano': 'piano', 'acoustic_guitar': 'acoustic guitar', 'electric_guitar': 'electric guitar',
               'strings': 'string ensemble', 'bass': 'bass guitar', 'drums': 'drum kit',
               'synth': 'synthesizer', 'guzheng': 'guzheng', 'flute': 'flute'}


def normalize_preferences(data):
    gender, tone = data.get('voice_gender', 'auto'), data.get('voice_tone', 'auto')
    instruments = data.get('instruments', [])
    if not isinstance(gender, str) or gender not in GENDERS or not isinstance(tone, str) or tone not in TONES:
        raise ValueError('请选择列表中的人声类型和音色。')
    if (not isinstance(instruments, list) or len(instruments) > 3
            or any(not isinstance(value, str) or value not in INSTRUMENTS for value in instruments)
            or len(set(instruments)) != len(instruments)):
        raise ValueError('主要乐器请选择列表中的至多 3 种，不要重复。')
    if data.get('mode') == 'bgm':
        gender = tone = 'auto'
    return {'voice_gender': gender, 'voice_tone': tone, 'instruments': sorted(instruments)}


def caption_preferences(job):
    parts = []
    if job.get('mode') == 'song':
        parts.extend(value for value in (GENDERS[job.get('voice_gender', 'auto')], TONES[job.get('voice_tone', 'auto')]) if value)
    selected = job.get('instruments', [])
    if selected:
        parts.append('featured instruments: ' + ', '.join(INSTRUMENTS[value] for value in selected))
    return '; '.join(parts)
