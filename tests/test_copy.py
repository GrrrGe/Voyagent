from pathlib import Path
import pytest
from scripts.lint_copy import scan
from tools.copy_policy import violations


def test_repository_copy():
    assert scan() == []

@pytest.mark.parametrize('text', ['Bad\u2013copy', 'Bad\u2014copy', 'An UNLOCK button', 'A hidden gem', "In today\u2019s world"])
def test_banned_copy_is_caught(text):
    assert violations(text)

def test_lint_finds_templates_and_prompts(tmp_path):
    for directory, name in [('templates', 'test.html'), ('static', 'test.js'), ('prompts', 'test.txt')]:
        path = tmp_path / directory / name
        path.parent.mkdir()
        path.write_text('bad\u2014copy')
    assert len(scan(tmp_path)) == 3

def test_escaped_dashes_are_caught(tmp_path):
    directory = tmp_path / 'static'
    directory.mkdir()
    (directory / 'test.js').write_text(r'const copy = "bad\u2014copy";')
    assert scan(tmp_path)
