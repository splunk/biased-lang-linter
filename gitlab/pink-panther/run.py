import csv
import os
import argparse
from subprocess import call
from utils.utils import get_colors_sh

c = get_colors_sh()


# Parse params
parser = argparse.ArgumentParser()
parser.add_argument('--path')
parser.add_argument('--mode')
parser.add_argument('--excluded_dirs_path')
parser.add_argument('--excluded_files_path')
parser.add_argument('--verbose', action='store_true')
args = parser.parse_args()
path = args.path
if not path:
    raise Exception('No path specified')
if path.endswith('/'):
    path = path[:-1]
mode = None
if args.mode == 'check':
    mode = 'check'
elif args.mode == 'fix':
    mode = 'fix'
if not mode:
    raise Exception('Invalid mode specified')
verbose = "" if args.verbose else "l"

# Read CSV file
lines = None
with open("word_list.csv") as fp:
    reader = csv.reader(fp, delimiter=",", quotechar='"')
    lines = [row for row in reader]



# Get excluded dirs
excluded_dirs=''
with open('.excluded_dirs', 'r') as excluded_dirsF:
    for line in excluded_dirsF:
        if excluded_dirs == '':
            excluded_dirs += line.rstrip()
        else:
            excluded_dirs += (',%s' % line).rstrip()
if args.excluded_dirs_path:
    target_path = '%s/%s' % (path, args.excluded_dirs_path)
    with open(target_path, 'r') as excluded_dirsF:
        for line in excluded_dirsF:
            if excluded_dirs == '':
                excluded_dirs += line.rstrip()
            else:
                excluded_dirs += (',%s' % line).rstrip()

# Get excluded files
excluded_files_args=''
with open('.excluded_files', 'r') as excluded_files_argsF:
    for line in excluded_files_argsF:
        if excluded_files_args == '':
            excluded_files_args += f'--exclude="{line.rstrip()}"'
        else:
            excluded_files_args += f' --exclude="{line.rstrip()}"'

if args.excluded_files_path:
    target_path = '%s/%s' % (path, args.excluded_files_path)
    with open(target_path, 'r') as custom_files:
        for line in custom_files:
            if excluded_files_args == '':
                excluded_files_args += f'--exclude="{line.rstrip()}"'
            else:
                excluded_files_args += f' --exclude="{line.rstrip()}"'

# Ternary operator check if excluded_dirs is empty, if not add str of excluded_dirs
excluded_dirs_arg = f'--exclude-dir={{{excluded_dirs}}}' if excluded_dirs != '' else ''

if mode == 'check':
    # Generate check.sh contents
    with open('check.sh', 'w+') as shell:
        # create var
        shell.write('fail=false\n\n')
        for line in lines:
            banned_word = line[0]

            shell.write(
                'echo "%sLooking for occurrences of banned word \'%s\':%s"\n' %
                (c['underline']['lightmagenta'], banned_word, c['text']['nc'])
            )
            shell.write(
                f'if fgrep {excluded_dirs_arg} {excluded_files_args} --color=always -{verbose}rni {path} -e \'{banned_word}\'; then\n'
            )
            shell.write('\tfail=true\n')
            shell.write('else\n')
            shell.write('\techo "%sNo occurences found. %s"\n' % (c['text']['orange'], c['text']['nc']))
            shell.write('fi\n\n')
        # add final error check
        shell.write('if $fail; then\n')
        shell.write('\techo "%sError: %sPink Panther%s found banned words. Replacement(s) required. %s"\n' % (c['text']['red'], c['text']['lightmagenta'], c['text']['red'], c['text']['nc']))
        shell.write('\texit 1;\n')
        shell.write('else\n')
        shell.write('\techo "%sPink panther %sfound no banned words! %s"\n' % (c['text']['lightmagenta'], c['text']['green'], c['text']['nc']))
        shell.write('fi\n')

    os.chmod('check.sh', 0o755)
    exit_code = call('./check.sh', shell=True)
    if exit_code == 1:
        raise Exception('Banned words found. Replacement(s) required.')
elif mode == 'fix':
    # Generate fix.sh contents
    with open('fix.sh', 'w+') as shell:
        for line in lines:
            banned_word = line[0]
            suggested = line[1].split(',')

            # if 1 suggestion, replace both lowercase + uppercase instances
            if len(suggested) == 1:
                shell.write(
                    'echo "%sReplacing occurrences of banned word \'%s\' with \'%s\' %s"\n' %
                    (c['text']['orange'], banned_word, suggested[0], c['text']['nc'])
                )
                shell.write(
                    f'fgrep {excluded_dirs_arg} {excluded_files_args} --color=always -lrn {path} -e \'{banned_word}\' | xargs sed -i "" \'s/{banned_word}/{suggested[0]}/g\';\n'
                )
                shell.write(
                    f'fgrep {excluded_dirs_arg} {excluded_files_args} --color=always -lrn {path} -e \'{banned_word.capitalize()}\' | xargs sed -i "" \'s/{banned_word.capitalize()}/{suggested[0].capitalize()}/g\';\n\n'
                )
            # if multiple suggestions, do not replace
            else:
                shell.write(
                    f'echo "%sBanned word \'%s\' requires manual replacement. Consider the words %s %s"\n' % (c['text']['yellow'], banned_word, suggested, c['text']['nc'])
                )
                shell.write(
                    f'fgrep {excluded_dirs_arg} {excluded_files_args} --color=always -lrn {path} -e \'{banned_word}\';\n\n'
                )
    os.chmod('fix.sh', 0o755)
    call('./fix.sh', shell=True)
