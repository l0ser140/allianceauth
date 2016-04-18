from django.conf import settings

from services.managers.util.ts3 import TS3Server
from services.models import TSgroup
from authentication.managers import AuthServicesInfoManager

import logging

logger = logging.getLogger(__name__)

class Teamspeak3Manager:

    def __init__(self):
        pass

    @staticmethod
    def __get_created_server():
        server = TS3Server(settings.TEAMSPEAK3_SERVER_IP, settings.TEAMSPEAK3_SERVER_PORT)
        server.login(settings.TEAMSPEAK3_SERVERQUERY_USER, settings.TEAMSPEAK3_SERVERQUERY_PASSWORD)
        server.use(settings.TEAMSPEAK3_VIRTUAL_SERVER)
        logger.debug("Got TS3 server instance based on settings.")
        return server

    @staticmethod
    def generate_username(username, corp_ticker):
        return settings.TEAMSPEAK3_NICKNAME_PATTERN % {'CORP': corp_ticker, 'NAME': username}

    @staticmethod
    def _get_userid(uid):
        logger.debug("Looking for uid %s on TS3 server." % uid)
        server = Teamspeak3Manager.__get_created_server()
        ret = server.send_command('clientdbfind', keys={'pattern': uid}, opts={'uid'})
        if ret and 'keys' in ret and 'cldbid' in ret['keys']:
            logger.debug("Got userid %s for uid %s" % (ret['keys']['cldbid'], uid))
            return ret['keys']['cldbid']

    @staticmethod
    def _group_id_by_name(groupname):
        server = Teamspeak3Manager.__get_created_server()
        logger.debug("Looking for group %s on TS3 server." % groupname)
        group_cache = server.send_command('servergrouplist')
        logger.debug("Received group cache from server: %s" % group_cache)
        for group in group_cache:
            logger.debug("Checking group %s" % group)
            if group['keys']['name'] == groupname:
                logger.debug("Found group %s, returning id %s" % (groupname, group['keys']['sgid']))
                return group['keys']['sgid']
        logger.debug("Group %s not found on server." % groupname)
        return None

    @staticmethod
    def _create_group(groupname):
        logger.debug("Creating group %s on TS3 server." % groupname)
        server = Teamspeak3Manager.__get_created_server()
        sgid = Teamspeak3Manager._group_id_by_name(groupname)
        if not sgid:
            logger.debug("Group does not yet exist. Proceeding with creation.")
            ret = server.send_command('servergroupadd', {'name': groupname})
            Teamspeak3Manager.__group_cache = None
            sgid = ret['keys']['sgid']
            server.send_command('servergroupaddperm',
                                {'sgid': sgid, 'permsid': 'i_group_needed_modify_power', 'permvalue': 75,
                                 'permnegated': 0, 'permskip': 0})
            server.send_command('servergroupaddperm',
                                {'sgid': sgid, 'permsid': 'i_group_needed_member_add_power', 'permvalue': 100,
                                 'permnegated': 0, 'permskip': 0})
            server.send_command('servergroupaddperm',
                                {'sgid': sgid, 'permsid': 'i_group_needed_member_remove_power', 'permvalue': 100,
                                 'permnegated': 0, 'permskip': 0})
        logger.info("Created group on TS3 server with name %s and id %s" % (groupname, sgid))
        return sgid

    @staticmethod
    def _user_group_list(cldbid):
        logger.debug("Retrieving group list for user with id %s" % cldbid)
        server = Teamspeak3Manager.__get_created_server()
        groups = server.send_command('servergroupsbyclientid', {'cldbid': cldbid})
        logger.debug("Retrieved group list: %s" % groups)
        outlist = {}

        if type(groups) == list:
            logger.debug("Recieved multiple groups. Iterating.")
            for group in groups:
                outlist[group['keys']['name']] = group['keys']['sgid']
        elif type(groups) == dict:
            logger.debug("Recieved single group.")
            outlist[groups['keys']['name']] = groups['keys']['sgid']
        logger.debug("Returning name/id pairing: %s" % outlist)
        return outlist

    @staticmethod
    def _group_list():
        logger.debug("Retrieving group list on TS3 server.")
        server = Teamspeak3Manager.__get_created_server()
        group_cache = server.send_command('servergrouplist')
        logger.debug("Received group cache from server: %s" % group_cache)
        outlist = {}
        if group_cache:
            for group in group_cache:
                logger.debug("Assigning name/id dict: %s = %s" % (group['keys']['name'], group['keys']['sgid']))
                outlist[group['keys']['name']] = group['keys']['sgid']
        else:
            logger.error("Received empty group cache while retrieving group cache from TS3 server. 1024 error.")
        logger.debug("Returning name/id pairing: %s" % outlist)
        return outlist

    @staticmethod
    def _add_user_to_group(uid, groupid):
        logger.debug("Adding group id %s to TS3 user id %s" % (groupid, uid))
        server = Teamspeak3Manager.__get_created_server()
        server_groups = Teamspeak3Manager._group_list()
        user_groups = Teamspeak3Manager._user_group_list(uid)
        
        if not groupid in user_groups.values():
            logger.debug("User does not have group already. Issuing command to add.")
            server.send_command('servergroupaddclient',
                                {'sgid': str(groupid), 'cldbid': uid})
            logger.info("Added user id %s to group id %s on TS3 server." % (uid, groupid))

    @staticmethod
    def _remove_user_from_group(uid, groupid):
        logger.debug("Removing group id %s from TS3 user id %s" % (groupid, uid))
        server = Teamspeak3Manager.__get_created_server()
        server_groups = Teamspeak3Manager._group_list()
        user_groups = Teamspeak3Manager._user_group_list(uid)

        if str(groupid) in user_groups.values():
            logger.debug("User is in group. Issuing command to remove.")
            server.send_command('servergroupdelclient',
                                {'sgid': str(groupid), 'cldbid': uid})
            logger.info("Removed user id %s from group id %s on TS3 server." % (uid, groupid))

    @staticmethod
    def _sync_ts_group_db():
        logger.debug("_sync_ts_group_db function called.")
        try:
            remote_groups = Teamspeak3Manager._group_list()
            local_groups = TSgroup.objects.all()
            logger.debug("Comparing remote groups to TSgroup objects: %s" % local_groups)
            for key in remote_groups:
                logger.debug("Typecasting remote_group value at position %s to int: %s" % (key, remote_groups[key]))
                remote_groups[key] = int(remote_groups[key])
            
            for group in local_groups:
                logger.debug("Checking local group %s" % group)
                if group.ts_group_id not in remote_groups.values():
                    logger.debug("Local group id %s not found on server. Deleting model %s" % (group.ts_group_id, group))
                    TSgroup.objects.filter(ts_group_id=group.ts_group_id).delete()
            for key in remote_groups:
                g = TSgroup(ts_group_id=remote_groups[key],ts_group_name=key)
                q = TSgroup.objects.filter(ts_group_id=g.ts_group_id)
                if not q:
                    logger.debug("Local group does not exist for TS group %s. Creating TSgroup model %s" % (remote_groups[key], g))
                    g.save()
        except:
            logger.exception("An unhandled exception has occured while syncing TS groups.")
            pass

    @staticmethod
    def _nicknames_check():
        logger.debug("_nicknames_check function called.")
        try:
            server = Teamspeak3Manager.__get_created_server()
            response = server.send_command('clientlist', opts={'uid'})
            logger.debug("Got ts3 userlist %s" % str(response))
            ts_users=[]
            if len(response) > 0:
                for item in response:
                    ts_users.append({'clid': item['keys']['clid'],
                                     'client_unique_identifier': item['keys']['client_unique_identifier'],
                                     'client_nickname': item['keys']['client_nickname']})

                auth_list = AuthServicesInfoManager.get_registered_in_ts3()
                for user in ts_users:
                    for auth in auth_list:
                        if user['client_unique_identifier'] == auth.teamspeak3_uid:
                            #detect wrong username
                            if user['client_nickname'] != auth.teamspeak3_username:
                                server.send_command('clientkick', {'clid': user['clid'], 'reasonid': 5,
                                            'reasonmsg': 'Wrong username. Expecting: %s' % auth.teamspeak3_username})
                        else:
                            #detect using registered username
                            if user['client_nickname'] == auth.teamspeak3_username:
                                server.send_command('clientkick', {'clid': user['clid'], 'reasonid': 5,
                                            'reasonmsg': 'Username registered for another unique identifier'})
        except:
            logger.exception("An unhandled exception has occured while TS nicknames check.")
            pass

    @staticmethod
    def add_user(username, corp_ticker):
        username = Teamspeak3Manager.generate_username(username, corp_ticker)
        uid = ""

        server = Teamspeak3Manager.__get_created_server()
        logger.debug("Search for user on TS3 server with username %s" % username)
        response = server.send_command('clientlist', opts={'uid'})

        try:
            if len(response) > 0:
                ts_user = filter(lambda person : person['keys']['client_nickname'] == username, response)
                if ts_user:
                    logger.debug("User %s found on TS3 server" % username)
                    ts_user = ts_user[0]['keys']
                    uid = ts_user['client_unique_identifier']
                    auth_exist = AuthServicesInfoManager.get_auth_service_info_by_teamspeak3(uid)
                    if auth_exist:
                        AuthServicesInfoManager.update_user_teamspeak3_info("", "", auth_exist.user)
                        logger.info("UID already registered for another user. Deactivating it. %s" % auth_exist.user)
                else:
                    logger.debug("User %s not found on TS3 server" % username)
                    return False, "User %s not found on TS3 server! Join the server before activate." % username
        except:
            logger.exception("Unable to add ts3 user %s" % username)
            return False, "Unable to add ts3 user %s"

        return True, username, uid

    @staticmethod
    def delete_user(uid):
        server = Teamspeak3Manager.__get_created_server()
        user = Teamspeak3Manager._get_userid(uid)
        logger.debug("Deleting user %s with id %s from TS3 server." % (user, uid))
        if user:
            for client in server.send_command('clientlist'):
                if client['keys']['client_database_id'] == user:
                    logger.debug("Found user %s on TS3 server - issuing deletion command." % user)
                    server.send_command('clientkick', {'clid': client['keys']['clid'], 'reasonid': 5,
                                                       'reasonmsg': 'Auth service deleted'})
            Teamspeak3Manager.update_groups(uid, {})
            return True
        else:
            logger.warn("User with id %s not found on TS3 server. Assuming succesful deletion." % uid)
            return True

    @staticmethod
    def reactivate(username, corp_ticker, uid_old):
        username = Teamspeak3Manager.generate_username(username, corp_ticker)
        uid = ""

        server = Teamspeak3Manager.__get_created_server()
        logger.debug("Search for user on TS3 server with username %s" % username)
        response = server.send_command('clientlist', opts={'uid'})

        try:
            if len(response) > 0:
                ts_user = filter(lambda person : person['keys']['client_nickname'] == username, response)
                if ts_user:
                    logger.debug("User %s found on TS3 server" % username)
                    ts_user = ts_user[0]['keys']
                    uid = ts_user['client_unique_identifier']
                    if uid != uid_old:
                        logger.info("Deactivating old UID %s" % uid_old)
                        Teamspeak3Manager.delete_user(uid_old)

                    auth_exist = AuthServicesInfoManager.get_auth_service_info_by_teamspeak3(uid)
                    if auth_exist:
                        AuthServicesInfoManager.update_user_teamspeak3_info("", "", auth_exist.user)
                        logger.info("UID already registered for another user. Deactivating it. %s" % auth_exist.user)

                else:
                    logger.debug("User %s not found on TS3 server" % username)
                    return False, "User %s not found on TS3 server! Join the server before reactivate." % username
        except:
            logger.exception("Unable to reactivate ts3 user %s" % username)
            return False, "Unable to reactivate ts3 user %s"

        return True, username, uid

    @staticmethod
    def kick_username(username):
        server = Teamspeak3Manager.__get_created_server()
        logger.debug("Trying to kick user %s from TS3 server." % username)
        response = server.send_command('clientlist')
        try:
            if len(response) > 0:
                ts_user = filter(lambda person : person['keys']['client_nickname'] == username, response)
                if ts_user:
                    server.send_command('clientkick', {'clid': ts_user[0]['keys']['clid'], 'reasonid': 5,
                                                       'reasonmsg': 'Auth service kick request'})
                    logger.debug("User %s succesfully kicked." % username)
                    return True, "User %s succesfully kicked." % username
                else:
                    logger.debug("User %s not found on server." % username)
                    return False, "User %s not found on server." % username

        except:
            logger.exception("Unable to kick ts3 user %s" % username)
            return False, "Unable to kick ts3 user %s" % username


    @staticmethod
    def update_groups(uid, ts_groups):
        logger.debug("Updating uid %s TS3 groups %s" % (uid, ts_groups))
        userid = Teamspeak3Manager._get_userid(uid)
        addgroups = []
        remgroups = []
        if userid is not None:
            user_ts_groups = Teamspeak3Manager._user_group_list(userid)
            logger.debug("User has groups on TS3 server: %s" % user_ts_groups)
            for key in user_ts_groups:
                user_ts_groups[key] = int(user_ts_groups[key])
            for ts_group_key in ts_groups:
                logger.debug("Checking if user has group %s on TS3 server." % ts_group_key)
                if ts_groups[ts_group_key] not in user_ts_groups.values():
                    addgroups.append(ts_groups[ts_group_key])
            for user_ts_group_key in user_ts_groups:
                if user_ts_groups[user_ts_group_key] not in ts_groups.values():
                    remgroups.append(user_ts_groups[user_ts_group_key])

            for g in addgroups:
                logger.info("Adding Teamspeak user %s into group %s" % (userid, g))
                Teamspeak3Manager._add_user_to_group(userid, g)

            for g in remgroups:
                logger.info("Removing Teamspeak user %s from group %s" % (userid, g))
                Teamspeak3Manager._remove_user_from_group(userid, g)

