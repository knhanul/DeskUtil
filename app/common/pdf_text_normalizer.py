import re
import unicodedata


def collect_raw_chars(raw_dict, page_num, excluded_bounds=None):
    chars = []
    for block in raw_dict.get('blocks', []):
        if excluded_bounds is not None and block.get('type') != 0:
            continue
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                for char in span.get('chars', []):
                    bbox = char['bbox']
                    if excluded_bounds is not None:
                        top, bottom = excluded_bounds
                        if bbox[3] <= top or bbox[1] >= bottom:
                            continue
                    chars.append({
                        'char': unicodedata.normalize('NFC', char['c']),
                        'bbox': bbox, 'y': bbox[1], 'x': bbox[0], 'page': page_num,
                    })
    return chars


def normalize_raw_chars(raw_chars, page_aware=False):
    if not raw_chars:
        return [], ''
    raw_chars.sort(key=(lambda char: (char['page'], char['y'])) if page_aware
                   else (lambda char: char['y']))
    grouped = []
    curr = [raw_chars[0]]
    for i in range(1, len(raw_chars)):
        if page_aware:
            same_line = (raw_chars[i]['page'] == curr[-1]['page']
                         and abs(raw_chars[i]['y'] - curr[-1]['y']) < 5.0)
        else:
            same_line = raw_chars[i]['y'] - curr[-1]['y'] < 5.0
        if same_line:
            curr.append(raw_chars[i])
        else:
            grouped.append(curr)
            curr = [raw_chars[i]]
    grouped.append(curr)

    final_norm = []
    raw_lines = []
    word_counter = 0
    for line in grouped:
        line.sort(key=lambda char: char['x'])
        line_str_raw = []
        word_counter += 1
        page_num = line[0]['page']
        for i, char in enumerate(line):
            line_str_raw.append(char['char'])
            if i > 0 and (line[i - 1]['char'].strip() == ''
                          or abs(char['x'] - line[i - 1]['bbox'][2]) > 2.5):
                word_counter += 1
            clean_char = char['char'].lower().strip()
            if not re.match(r'[가-힣a-z0-9.,?!;:()\-\[\]{}\'"]', clean_char):
                continue
            if not final_norm or not (clean_char == final_norm[-1]['char']
                                      and abs(char['x'] - final_norm[-1]['x']) < 2.5):
                final_norm.append({
                    'char': clean_char, 'bbox': char['bbox'], 'x': char['x'],
                    'y': char['y'], 'page': page_num, 'word_id': word_counter,
                })
        raw_lines.append(''.join(line_str_raw))
    return final_norm, '\n'.join(raw_lines)
