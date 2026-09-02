import zipfile
import xml.etree.ElementTree as ET

def read_docx(file_path):
    with zipfile.ZipFile(file_path) as docx:
        tree = ET.fromstring(docx.read('word/document.xml'))
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        text = []
        for p in tree.iterfind('.//w:p', namespaces):
            p_text = ''.join(node.text for node in p.iterfind('.//w:t', namespaces) if node.text)
            if p_text:
                text.append(p_text)
        return '\n'.join(text)

if __name__ == '__main__':
    content = read_docx('data/reference/struktur html.docx')
    with open('data/reference/struktur_html_extracted.txt', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success, length:", len(content))
