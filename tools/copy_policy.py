"""Copy policy shared by the lint command and provider output validation."""
import re
BANNED = ('seamless', 'vibrant', 'nestled', 'bustling', 'hidden gem', 'tapestry',
          'delve', 'unlock', 'elevate', 'breathtaking', 'look no further', "in today's",
          'moreover', 'furthermore', 'additionally', 'game changer', 'Важно')

def violations(text):
    found = [f'U+{ord(c):04X}' for c in ('\u2013', '\u2014') if c in text]
    normalized = text.casefold().replace('\u2019', "'")
    return found + [word for word in BANNED if re.search(r'(?<!\w)' + re.escape(word.casefold()) + r'(?!\w)', normalized)]

def clean_output(text):
    text = str(text).replace('\u2013', ',').replace('\u2014', ',')
    for word in BANNED:
        text = re.sub(re.escape(word), '', text, flags=re.I)
    return text[:1600]
