#!/usr/bin/env python3


import os
import subprocess
import shutil
import click
import json
import pyperclip
from pathlib import Path
from time import sleep

TEMPLATE = os.path.dirname(os.path.realpath(__file__)) + '/template.svg'
OPEN_VIM_BUFFER = '''
                  tell application "iTerm2"
                      set newWindow to (create window with default profile)
                      set bounds of front window to {60, 690, 700, 800}
                      tell current session of newWindow
                          write text "vim-text"
                      end tell
                  end tell
                  '''
BLUE = '85c1e9'


class NotRunningException(Exception):
    pass


@click.group()
def cli():
    pass


def simplify_title(title):
    return title.strip(' ').replace(' ', '-').lower()


def beautify_title(title):
    return title.replace('-', ' ').title()[:-4]


def get_json(command):
    raw_query, _ = subprocess.Popen(command,
                                    stdout=subprocess.PIPE).communicate()
    return json.loads(raw_query)


def get_focused_desktop():
    query = get_json(['yabai', '-m', 'query', '--spaces'])
    for item in query:
        if item['focused'] == 1:
            return item['index']


def get_new_desktop():
    query = get_json(['yabai', '-m', 'query', '--spaces'])
    return len(query)


def increment_file_copy(filename):
    try:
        return filename[:-1] + f'{int(filename[-1]) + 1}'
    except ValueError:
        return filename + '-1'


def run_commands(commands):
    for command in commands:
        subprocess.run(command)


def inkscape(path):
    current_desktop = str(get_focused_desktop())
    commands = [['yabai', '-m', 'space', '--create'],
                ['yabai', '-m', 'space', '--focus',
                 str(get_new_desktop() + 1)],
                ['yabai', '-m', 'space', '--layout', 'float'],
                ['inkscape', path],
                ['yabai', '-m', 'space', '--destroy'],
                ['yabai', '-m', 'space', '--focus', current_desktop]]
    run_commands(commands)


def export_pdf(path):
    svgs = [item[:-4] for item in os.listdir(path) if item[-4:] == '.svg']
    for item in svgs:
        file_path = path + item
        if not os.path.isfile(file_path + '.pdf'):
            subprocess.run(['inkscape', '-f', file_path + '.svg',
                            '-A', file_path + '.pdf', '--export-latex'])


def is_running(process):
    return subprocess.Popen(['pgrep', '-x', process],
                            stdout=subprocess.PIPE).communicate()[0]


def invoke_choose(path):
    figures = [item for item in os.listdir(path)
               if item[-4:] == '.svg']
    options = ''.join(beautify_title(item) + '\n'
                      for item in figures)
    result, _ = subprocess.Popen(f'echo "{options}" | choose -c {BLUE}',
                                 shell=True,
                                 stdout=subprocess.PIPE).communicate()
    return simplify_title(str(result)[2:-1])


@cli.command()
@click.argument('title')
@click.argument('path')
def create_figure(title, path):
    if not os.path.isdir(path + '/figures/'):
        os.mkdir(path + '/figures/')

    filename = simplify_title(title)
    figure_path = [path, '/figures/', filename, '.svg']

    if os.path.isfile(''.join(figure_path)):
        filename = increment_file_copy(filename)
        figure_path[2] = filename

    figure_path = ''.join(figure_path)
    shutil.copyfile(TEMPLATE, figure_path)
    inkscape(figure_path)
    export_pdf(path + '/figures/')
    pyperclip.copy(filename)


@cli.command()
def insert_latex():
    if not is_running('inkscape-bin'):
        raise NotRunningException

    buffer_path = '/tmp/latex-temp.text'
    Path(buffer_path).touch()
    args = [item for x in [("-e", l.strip())
                           for l in OPEN_VIM_BUFFER.split('\n')
                           if l.strip() != ''] for item in x]
    subprocess.run(["osascript"] + args)
    while os.stat(buffer_path).st_size == 0:
        sleep(0.01)
    subprocess.run("tmux kill-pane", shell=True)
    subprocess.run("osascript -e 'tell application \"System Events\" to tell \
                   process \"XQuartz\" to set frontmost to true'", shell=True)
    subprocess.run(f"head -n 1 {buffer_path} | \
                    tr -d '\n' | pbcopy", shell=True)
    sleep(0.1)
    subprocess.run("osascript -e 'tell application \"System Events\" \
                   to keystroke \"v\" using control down'", shell=True)
    os.remove(buffer_path)


@cli.command()
@click.argument('path')
def edit_figure(path):
    figures_path = path + '/figures/'
    result = invoke_choose(figures_path)
    if result:
        figure_path = figures_path + result + '.svg'
        inkscape(figure_path)
        subprocess.run(['inkscape', '-f', figure_path, '-A',
                        figure_path[:-4] + '.pdf', '--export-latex'])


@cli.command()
@click.argument('path')
def delete_figure(path):
    figures_path = path + '/figures/'
    result = invoke_choose(figures_path)
    if result:
        file_path = figures_path + result
        commands = [['rm', file_path + '.svg'],
                    ['rm', file_path + '.pdf'],
                    ['rm', file_path + '.pdf_tex']]
        run_commands(commands)


if __name__ == '__main__':
    cli()
