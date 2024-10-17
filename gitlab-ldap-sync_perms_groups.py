#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gitlab
import sys
import json
import ldap
import ldap.asyncsearch
import logging

if __name__ == "__main__":
    print('Initializing gitlab-ldap-sync-perms_groups.')
    config = None
    with open('config.json') as f:
        config = json.load(f)
    if config is not None:
        print('Done.')
        print('Updating logger configuration')
        if not config['gitlab']['group_visibility']:
            config['gitlab']['group_visibility'] = 'private'
        log_option = {
            'format': '[%(asctime)s] [%(levelname)s] %(message)s'
        }
        if config['log']:
            log_option['filename'] = config['log']
        if config['log_level']:
            log_option['level'] = getattr(logging, str(config['log_level']).upper())
        logging.basicConfig(**log_option)
        print('Done.')
        logging.info('Connecting to GitLab')
        if config['gitlab']['api']:
            gl = None
            if not config['gitlab']['private_token'] and not config['gitlab']['oauth_token']:
                logging.error('You should set at least one auth information in config.json, aborting.')
            elif config['gitlab']['private_token'] and config['gitlab']['oauth_token']:
                logging.error('You should set at most one auth information in config.json, aborting.')
            else:
                if config['gitlab']['private_token']:
                    gl = gitlab.Gitlab(url=config['gitlab']['api'], private_token=config['gitlab']['private_token'], ssl_verify=config['gitlab']['ssl_verify'])
                elif config['gitlab']['oauth_token']:
                    gl = gitlab.Gitlab(url=config['gitlab']['api'], oauth_token=config['gitlab']['oauth_token'], ssl_verify=config['gitlab']['ssl_verify'])
                else:
                    gl = None
                if gl is None:
                    logging.error('Cannot create gitlab object, aborting.')
                    sys.exit(1)
            gl.auth()
            logging.info('Done.')

            logging.info('Connecting to LDAP')
            if not config['ldap']['url']:
                logging.error('You should configure LDAP in config.json')
                sys.exit(1)

            try:
                l = ldap.initialize(uri=config['ldap']['url'])
                l.simple_bind_s(config['ldap']['bind_dn'], config['ldap']['password'])
            except:
                logging.error('Error while connecting')
                sys.exit(1)

            logging.info('Done.')

            logging.info('Getting all groups from GitLab.')
            gitlab_groups = []
            gitlab_groups_names = []
            for group in gl.groups.list(all=True):
                gitlab_groups_names.append(group.full_name)
                gitlab_group = {"name": group.full_name, "members": []}
                for member in group.members.list(all=True):
                    user = gl.users.get(member.id)
                    if user.identities and len(user.identities) > 0 and 'extern_uid' in user.identities[0]:
                        gitlab_group['members'].append({
                           'username': user.username,
                           'name': user.name,
                           'identities': user.identities[0]['extern_uid'],
                           'email': user.email
                        })
                        logging.debug("User {user.username} does have a valid 'extern_uid' in identities.")
                    else:
                        logging.debug("User {user.username} does not have a valid 'extern_uid' in identities.")
                gitlab_groups.append(gitlab_group)

            logging.info('Done.')

            logging.info('Getting all groups from LDAP.')
            ldap_groups = []
            ldap_groups_names = []
            if not config['ldap']['group_attribute'] and not config['ldap']['group_prefix']:
                filterstr = '(objectClass=group)'
            else:
                if config['ldap']['group_attribute'] and config['ldap']['group_prefix']:
                    logging.error('You should set "group_attribute" or "group_prefix" but not both in config.json')
                    sys.exit(1)
                else:
                    if config['ldap']['group_attribute']:
                        filterstr = '(&(objectClass=group)(%s=gitlab_sync))' % config['ldap']['group_attribute']
                    if config['ldap']['group_prefix']:
                        filterstr = '(&(objectClass=%s)(cn=%s*))' % (config['ldap']['group_ObjectClass'], config['ldap']['group_prefix'])
            attrlist=[config['ldap']['group_AttributeForName'], 'member']
            if config['gitlab']['add_description']:
                attrlist.append('description')
            for group_dn, group_data in l.search_s(base=config['ldap']['groups_base_dn'],
                                                   scope=ldap.SCOPE_SUBTREE,
                                                   filterstr=filterstr,
                                                   attrlist=attrlist):
                ldap_groups_names.append(group_data[config['ldap']['group_AttributeForName']][0].decode())
                ldap_group = {"name": group_data[config['ldap']['group_AttributeForName']][0].decode(), "members": []}
                if config['gitlab']['add_description'] and 'description' in group_data:
                    ldap_group.update({"description": group_data['description'][0].decode()})
                if 'member' in group_data:
                    for member in group_data['member']:
                        member = member.decode()
                        for user_dn, user_data in l.search_s(base=member,
                                                             scope=ldap.SCOPE_BASE,
                                                             filterstr='(objectClass=*)',
                                                             attrlist=['uid', 'mail', 'cn']):
                            if 'sAMAccountName' in user_data:
                                username = user_data['sAMAccountName'][0].decode()
                            else:
                                username = user_data['uid'][0].decode()
                            ldap_group['members'].append({
                                'username': username,
                                'name': user_data[config['ldap']['user_AttributeForName']][0].decode(),
                                'identities': str(member).lower(),
                                'email': user_data['mail'][0].decode()
                            })
                ldap_groups.append(ldap_group)
            logging.info('Done.')

            logging.info('Groups currently in GitLab : %s' % str.join(', ', gitlab_groups_names))
            logging.info('Groups currently in LDAP : %s' % str.join(', ', ldap_groups_names))

            logging.info('Syncing members AND permissions in GitLab groups from LDAP groups.')

            access_levels = {
                "GUEST": gitlab.const.AccessLevel.GUEST,
                "REPORTER": gitlab.const.AccessLevel.REPORTER,
                "DEVELOPER": gitlab.const.AccessLevel.DEVELOPER,
                "MAINTAINER": gitlab.const.AccessLevel.MAINTAINER,
                "OWNER": gitlab.const.AccessLevel.OWNER
            }

            for entry in config['sync']['matrix']:
                ldap_source_group, gitlab_destination_group, permissions = entry
                logging.debug('Current source LDAP group: %s' % ldap_source_group)
                logging.debug('Current destination GitLab group: %s' % gitlab_destination_group)
                logging.debug('Current permissions to assign: %s' % permissions)

                access_level = access_levels.get(permissions)
                if access_level is None:
                    logging.error('Unknown permission, aborting.')
                    sys.exit(1)

                for l_group in ldap_groups:
                    if ldap_source_group == l_group['name']:
                        for l_member in l_group['members']:
                            if l_member not in gitlab_groups[gitlab_groups_names.index(gitlab_destination_group)]['members']:
                                logging.info('|  |- User %s is member in LDAP but not in GitLab, updating GitLab.' % l_member['name'])
                                # Line below can most likely be optimized and protected
                                g = [group for group in gl.groups.list(search=gitlab_destination_group) if group.name == gitlab_destination_group][0]
                                g.save()
                                u = gl.users.list(username=l_member['username'])
                                if len(u) > 0:
                                    u = u[0]
                                    if u not in g.members.list(all=True):
                                        g.members.create({'user_id': u.id, 'access_level': access_level})
                                    g.save()
                                else:
                                    if config['gitlab']['create_user']:
                                        logging.info('|  |- User %s does not exist in gitlab, creating.' % l_member['name'])
                                        try:
                                            u = gl.users.create({
                                                'email': l_member['email'],
                                                'name': l_member['name'],
                                                'username': l_member['username'],
                                                'extern_uid': l_member['identities'],
                                                'provider': config['gitlab']['ldap_provider'],
                                                'password': 'pouetpouet'
                                            })
                                        except gitlab.exceptions as e:
                                            if e.response_code == '409':
                                                u = gl.users.create({
                                                    'email': l_member['email'].replace('@', '+gl-%s@' % l_member['username']),
                                                    'name': l_member['name'],
                                                    'username': l_member['username'],
                                                    'extern_uid': l_member['identities'],
                                                    'provider': config['gitlab']['ldap_provider'],
                                                    'password': 'pouetpouet'
                                                })
                                        g.members.create({'user_id': u.id, 'access_level': access_level})
                                        g.save()
                                    else:
                                        logging.info('|  |- User %s does not exist in gitlab, skipping.' % l_member['name'])
                            else:
                                logging.info('|  |- User %s already in gitlab group, enforcing Access Level.' % l_member['name'])

                                # The sync matrix must list the groups from least privileged to most privileged,
                                # as the last line processed in the matrix will set the effective access level.

                                g = [group for group in gl.groups.list(search=gitlab_destination_group) if group.name == gitlab_destination_group][0]
                                g.save()
                                u = gl.users.list(username=l_member['username'])
                                if len(u) > 0:
                                    u = u[0]
                                    member = g.members.get(u.id)
                                    member.access_level = access_level
                                    member.save()
                                else:
                                    logging.info('|  |- User %s Access Level update failed.' % l_member['name'])
                        logging.info('Done.')
                       

            logging.info('Cleaning membership of LDAP Groups')

            l_syncdestgroups = list(set(entry[1] for entry in config['sync']['matrix']))

            for g_group in gitlab_groups:
                logging.info('Working on group %s ...' % g_group['name'])
                if g_group['name'] in l_syncdestgroups:
                    logging.info('|- Working on group\'s members.')
                    for g_member in g_group['members']:
                        if str(config['ldap']['users_base_dn']).lower() not in g_member['identities']:
                            logging.info('|  |- Not a LDAP user, skipping.')
                        else:
                            b_present = False             
                            for entry in config['sync']['matrix']:
                                ldap_source_group, gitlab_destination_group, permissions = entry
                                logging.debug('Current source LDAP group: %s' % ldap_source_group)
                                logging.debug('Current destination GitLab group: %s' % gitlab_destination_group)
                                logging.debug('Current permissions to assign: %s' % permissions)
                                if gitlab_destination_group == g_group['name']:
                                    # FIXME: must implement a protection to check the source groups in the matrix exist in LDAP!!!
                                    if g_member in ldap_groups[ldap_groups_names.index(ldap_source_group)]['members']:
                                        b_present = True
                                        break

                            if b_present: 
                                logging.info('|  |- User %s still in one of the LDAP Groups, skipping.' % g_member['name'])
                            else:
                                logging.info('|  |- User %s no longer in LDAP Group, removing.' % g_member['name'])
                                g = [group for group in gl.groups.list(search=g_group['name']) if group.name == g_group['name']][0]
                                u = gl.users.list(username=g_member['username'])[0]
                                if u is not None:
                                    g.members.delete(u.id)
                                    g.save()

                    logging.info('|- Done.')
                else:
                    logging.info('|- Not a group with permissions controlled by LDAP groups, skipping.')
                logging.info('Done')
        else:
            logging.error('GitLab API is empty, aborting.')
            sys.exit(1)
    else:
        print('Could not load config.json, check if the file is present.')
        print('Aborting.')
        sys.exit(1)