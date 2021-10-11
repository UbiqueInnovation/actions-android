from datetime import datetime
import sys
import json
import os
import requests
import argparse
import re
import time


def upload(endpoint, json_map, files):
    print('Try uploading build info from json: \n')
    print(json.dumps(json_map))
    print('\n')
    result = requests.post(endpoint, params=json_map, files=files, timeout=120)
    print(result.status_code)
    print(result.text)
    print('\n')
    if result.status_code != 200:
        sys.exit('Uploading data failed')


def generate_json_dict(args):
    android_home = os.environ['ANDROID_HOME']
    build_tools = getBuildTools()
    print(build_tools)
    os.system('chmod +x {}/build-tools/{}/aapt'.format(android_home, build_tools))
    aapt = os.popen(
        '{}/build-tools/{}/aapt d badging {}'.format(android_home, build_tools, args.apk_file)).read().strip()
    print('aapt: ' + aapt)
    app_version = aapt.split('versionName=')[1].split(' ')[0]
    app_name = aapt.split('application-label:')[1].split(' ')[0]
    app_identifier = aapt.split('package: name=')[1].split(' ')[0]

    json_dict = {'platform': 'android', 'configuration': args.configuration,
                 'projectKey': args.project_key, 'app': args.app, 'provisioning': '',
                 'branch': args.branch.replace('origin/', ''), 'uuid': args.uuid, 'appIdentifier': app_identifier,
                 'appName': app_name, 'appVersion': app_version, 'build_time': round(time.time() * 1000),
                 'buildNr': args.build_nr}

    gitlog = os.popen('git log --pretty=format:\"%h%n%aN%n%aE%n%s%n\" -1').read().strip()
    print('Gitlog: ' + gitlog)
    gitlogs = gitlog.split('\n')
    comment = gitlogs[3]
    revision = gitlogs[0]
    user = gitlogs[2].split('@')[0]

    print(user + ':  ' + comment)
    json_dict['comment'] = comment
    json_dict['revNr'] = revision
    json_dict['user'] = user
    return json_dict


def generate_files_dict(args):
    apk = open(args.apk_file, 'rb')

    files = {'buildFile': apk}
    if os.path.isfile(args.desym_file):
        desym = open(args.desym_file, 'rb')
        files['desymFile'] = desym
    if os.path.isfile(args.icon_file):
        icon = open(args.icon_file, 'rb')
        files['buildIcon'] = icon
    return files


def getBuildTools():
    matchBuildVersion = re.compile("(\d{2})\.(\d)\.(\d)")
    tools = {}
    for root, dirs, files in os.walk(os.environ["ANDROID_HOME"] + "/build-tools"):
        for dir in dirs:
            if matchBuildVersion.match(dir):
                ms =  matchBuildVersion.match(dir)
                tools[(int(ms.group(1)), int(ms.group(2)), int(ms.group(3)))] = ms.string

    toolsList = list(tools.keys())
    toolsList.sort()
    toolsList.reverse()
    return tools[toolsList[0]]


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apk_file')
    parser.add_argument('--desym_file')
    parser.add_argument('--icon_file')
    parser.add_argument('--configuration')
    parser.add_argument('--project_key')
    parser.add_argument('--app')
    parser.add_argument('--branch')
    parser.add_argument('--uuid')
    parser.add_argument('--build_nr')
    parser.add_argument('--git_revision')
    parser.add_argument('--endpoint')
    args = parser.parse_args()

    upload(args.endpoint, generate_json_dict(args), generate_files_dict(args))
