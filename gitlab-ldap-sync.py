#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import gitlab
import sys
import json
import ldap
import ldap.asyncsearch

if __name__ == "__main__":
    print('Initializing gitlab-ldap-sync.')
    config = None
    with open('config.json') as f:
        config = json.load(f)
    if config is not None:
        print('Done.')
        print('Connecting to GitLab')
        if config['gitlab']['api']:
            gl = None
            if not config['gitlab']['private_token'] and not config['gitlab']['oauth_token']:
                print('You should set at least one auth information in config.json, aborting.')
            elif config['gitlab']['private_token'] and config['gitlab']['oauth_token']:
                print('You should set at most one auth information in config.json, aborting.')
            else:
                if config['gitlab']['private_token']:
                    gl = gitlab.Gitlab(url=config['gitlab']['api'], private_token=config['gitlab']['private_token'])
                elif config['gitlab']['oauth_token']:
                    gl = gitlab.Gitlab(url=config['gitlab']['api'], oauth_token=config['gitlab']['oauth_token'])
                else:
                    gl = None
                if gl is None:
                    print('Cannot create gitlab object, aborting.')
                    sys.exit(1)
            gl.auth()
            print('Done.')

            print('Connecting to LDAP')
            if not config['ldap']['url']:
                print('You should configure LDAP in config.json')
                sys.exit(1)

            try:
                l = ldap.initialize(uri=config['ldap']['url'], bytes_mode=False)
                l.simple_bind_s(config['ldap']['bind_dn'], config['ldap']['password'])
            except:
                print('Error while connecting')
                sys.exit(1)

            print('Done.')

            print('Getting all groups from GitLab.')
            gitlab_groups = []
            gitlab_groups_names = []
            for group in gl.groups.list():
                gitlab_groups_names.append(group.full_name)
                gitlab_group = {"name": group.full_name, "members": []}
                for member in group.members.list():
                    user = gl.users.get(member.id)
                    gitlab_group['members'].append({
                        'username': user.username,
                        'name': user.name,
                        'identities': user.identities[0]['extern_uid'],
                        'email': user.email
                    })
                gitlab_groups.append(gitlab_group)

            print('Done.')

            print('Getting all groups from LDAP.')
            ldap_groups = []
            ldap_groups_names = []
            for group_dn, group_data in l.search_s(base=config['ldap']['groups_base_dn'],
                                                   scope=ldap.SCOPE_SUBTREE,
                                                   filterstr=u'(objectClass=group)',
                                                   attrlist=[u'name', u'member']):
                ldap_groups_names.append(group_data['name'][0])
                ldap_group = {"name": group_data['name'][0], "members": []}
                if 'member' in group_data:
                    for member in group_data['member']:
                        for user_dn, user_data in l.search_s(base=config['ldap']['users_base_dn'],
                                                             scope=ldap.SCOPE_SUBTREE,
                                                             filterstr=u'(&(|(distinguishedName=%s)(dn=%s))(objectClass=user))' % (
                                                                     member,
                                                                     member),
                                                             attrlist=[u'uid', u'sAMAccountName', u'mail',
                                                                       u'displayName']):
                            if 'sAMAccountName' in user_data:
                                username = user_data['sAMAccountName'][0]
                            else:
                                username = user_data['uid'][0]
                            ldap_group['members'].append({
                                'username': username,
                                'name': user_data['displayName'][0],
                                'identities': str(member).lower(),
                                'email': user_data['mail'][0]
                            })
                ldap_groups.append(ldap_group)
            print('Done.')

            print('Groups currently in GitLab : %s' % str.join(', ', gitlab_groups_names))
            print('Groups currently in LDAP : %s' % str.join(', ', ldap_groups_names))

            print('Syncing Groups from LDAP.')

            for l_group in ldap_groups:
                print('Working on group %s ...' % l_group['name'])
                if l_group['name'] not in gitlab_groups_names:
                    print('\tGroup not existing in GitLab, creating.')
                    g = gl.groups.create({'name': l_group['name'], 'path': l_group['name']})
                    g.save()
                else:
                    print('|- Group already exist in GitLab, skiping creation.')

                print('|- Working on group\'s members.')
                for l_member in l_group['members']:
                    if l_member not in gitlab_groups[gitlab_groups_names.index(l_group['name'])]['members']:
                        print('|  |- User %s is member in LDAP but not in GitLab, updating GitLab.' % l_member['name'])
                        g = gl.groups.list(search=l_group['name'])[0]
                        u = gl.users.list(search=l_member['username'])[0]
                        if u is not None:
                            g.members.create({'user_id': u.id, 'access_level': gitlab.DEVELOPER_ACCESS})
                            g.save()
                        else:
                            print('|  |- User %s does not exist in gitlab, skipping.' % l_member['name'])
                    else:
                        print('|  |- User %s already in gitlab group, skipping.' % l_member['name'])
                print('Done.')

            print('Done.')

            print('Cleaning membership of LDAP Groups')

            for g_group in gitlab_groups:
                print('Working on group %s ...' % g_group['name'])
                if g_group['name'] in ldap_groups_names:
                    print('|- Working on group\'s members.')
                    for g_member in g_group['members']:
                        if g_member not in ldap_groups[ldap_groups_names.index(g_group['name'])]['members']:
                            if str(config['ldap']['users_base_dn']).lower() not in g_member['identities']:
                                print('|  |- Not a LDAP user, skipping.')
                            else:
                                print('|  |- User %s no longer in LDAP Group, removing.' % g_member['name'])
                                g = gl.groups.list(search=g_group['name'])[0]
                                u = gl.users.list(search=g_member['username'])[0]
                                if u is not None:
                                    g.members.delete(u.id)
                                    g.save()
                        else:
                            print('|  |- User %s still in LDAP Group, skipping.' % g_member['name'])
                    print('|- Done.')
                else:
                    print('|- Not a LDAP group, skipping.')
                print('Done')
        else:
            print('GitLab API is empty, aborting.')
            sys.exit(1)
    else:
        print('Could not load config.json, check if the file is present.')
        print('Aborting.')
        sys.exit(1)
