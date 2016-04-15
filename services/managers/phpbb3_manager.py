import os
import calendar
from datetime import datetime

from passlib.apps import phpbb3_context
from django.db import connections

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

class Phpbb3Manager:
    SQL_ADD_USER = r"INSERT INTO phpbb_users (username, username_clean, " \
                   r"user_password, user_email, group_id, user_regdate, user_permissions, " \
                   r"user_sig) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"

    SQL_UPD_USER = r"UPDATE phpbb_users SET user_email= %s, user_password=%s, username=%s WHERE username_clean = %s"

    SQL_UPD_CHAR = r"UPDATE phpbb_users SET username=%s WHERE username_clean = %s"

    SQL_UPD_USER_BY_CHAR = r"UPDATE phpbb_users SET user_email= %s, user_password=%s, username_clean=%s WHERE username = %s"

    SQL_DIS_USER = r"UPDATE phpbb_users SET username_clean = %s, user_email= %s, user_password=%s WHERE username_clean = %s"

    SQL_USER_ID_FROM_USERNAME = r"SELECT user_id from phpbb_users WHERE username_clean = %s"

    SQL_USER_FROM_CHARACTER = r"SELECT username_clean from phpbb_users WHERE username = %s"

    SQL_ADD_USER_GROUP = r"INSERT INTO phpbb_user_group (group_id, user_id, user_pending) VALUES (%s, %s, %s)"

    SQL_GET_GROUP_ID = r"SELECT group_id from phpbb_groups WHERE group_name = %s"

    SQL_ADD_GROUP = r"INSERT INTO phpbb_groups (group_name,group_desc,group_legend) VALUES (%s,%s,0)"

    SQL_UPDATE_USER_PASSWORD = r"UPDATE phpbb_users SET user_password = %s WHERE username_clean = %s"

    SQL_REMOVE_USER_GROUP = r"DELETE FROM phpbb_user_group WHERE user_id=%s AND group_id=%s "

    SQL_GET_ALL_GROUPS = r"SELECT group_id, group_name FROM phpbb_groups"

    SQL_GET_USER_GROUPS = r"SELECT phpbb_groups.group_name FROM phpbb_groups , phpbb_user_group WHERE " \
                          r"phpbb_user_group.group_id = phpbb_groups.group_id AND user_id=%s"

    SQL_ADD_USER_AVATAR = r"UPDATE phpbb_users SET user_avatar_type=2, user_avatar_width=128, user_avatar_height=128, user_avatar=%s WHERE user_id = %s"
    
    SQL_CLEAR_USER_PERMISSIONS = r"UPDATE phpbb_users SET user_permissions = '' WHERE user_Id = %s"

    SQL_DEL_SESSION = r"DELETE FROM phpbb_sessions where session_user_id = %s"

    SQL_DEL_AUTOLOGIN = r"DELETE FROM phpbb_sessions_keys where user_id = %s"

    def __init__(self):
        pass

    @staticmethod
    def __add_avatar(username_clean, characterid):
        logger.debug("Adding EVE character id %s portrait as phpbb avater for user %s" % (characterid, username_clean))
        avatar_url = "https://image.eveonline.com/Character/" + characterid + "_128.jpg"
        cursor = connections['phpbb3'].cursor()
        userid = Phpbb3Manager.__get_user_id(username_clean)
        cursor.execute(Phpbb3Manager.SQL_ADD_USER_AVATAR, [avatar_url, userid])

    @staticmethod
    def __generate_random_pass():
        return os.urandom(8).encode('hex')

    @staticmethod
    def __gen_hash(password):
        return phpbb3_context.encrypt(password)

    @staticmethod
    def __clean_username(username):
        return username.lower()

    @staticmethod
    def __get_group_id(groupname):
        logger.debug("Getting phpbb3 group id for groupname %s" % groupname)
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_GET_GROUP_ID, [groupname])
        row = cursor.fetchone()
        logger.debug("Got phpbb group id %s for groupname %s" % (row[0], groupname))
        return row[0]

    @staticmethod
    def __get_user_id(username_clean):
        logger.debug("Getting phpbb3 user id for username %s" % username_clean)
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_USER_ID_FROM_USERNAME, [username_clean])
        row = cursor.fetchone()
        if row is not None:
            logger.debug("Got phpbb user id %s for username %s" % (row[0], username_clean))
            return row[0]
        else:
            logger.error("Username %s not found on phpbb. Unable to determine user id." % username_clean)
            return None

    @staticmethod
    def __get_user_by_char(character):
        logger.debug("Getting phpbb3 user for character %s" % character)
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_USER_FROM_CHARACTER, [character])
        row = cursor.fetchone()
        if row is not None:
            logger.debug("Got phpbb user %s for character %s" % (row[0], character))
            return row[0]
        else:
            logger.error("Character %s not found on phpbb. Unable to determine user." % character)
            return None

    @staticmethod
    def __get_all_groups():
        logger.debug("Getting all phpbb3 groups.")
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_GET_ALL_GROUPS)
        rows = cursor.fetchall()
        out = {}
        for row in rows:
            out[row[1]] = row[0]
        logger.debug("Got phpbb groups %s" % out)
        return out

    @staticmethod
    def __get_user_groups(userid):
        logger.debug("Getting phpbb3 user id %s groups" % userid)
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_GET_USER_GROUPS, [userid])
        out = [row[0] for row in cursor.fetchall()]
        logger.debug("Got user %s phpbb groups %s" % (userid, out))
        return out

    @staticmethod
    def __get_current_utc_date():
        d = datetime.utcnow()
        unixtime = calendar.timegm(d.utctimetuple())
        return unixtime

    @staticmethod
    def __create_group(groupname):
        logger.debug("Creating phpbb3 group %s" % groupname)
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_ADD_GROUP, [groupname, groupname])
        logger.info("Created phpbb group %s" % groupname)
        return Phpbb3Manager.__get_group_id(groupname)

    @staticmethod
    def __add_user_to_group(userid, groupid):
        logger.debug("Adding phpbb3 user id %s to group id %s" % (userid, groupid))
        try:
            cursor = connections['phpbb3'].cursor()
            cursor.execute(Phpbb3Manager.SQL_ADD_USER_GROUP, [groupid, userid, 0])
            cursor.execute(Phpbb3Manager.SQL_CLEAR_USER_PERMISSIONS, [userid])
            logger.info("Added phpbb user id %s to group id %s" % (userid, groupid))
        except:
            logger.exception("Unable to add phpbb user id %s to group id %s" % (userid, groupid))
            pass

    @staticmethod
    def __remove_user_from_group(userid, groupid):
        logger.debug("Removing phpbb3 user id %s from group id %s" % (userid, groupid))
        try:
            cursor = connections['phpbb3'].cursor()
            cursor.execute(Phpbb3Manager.SQL_REMOVE_USER_GROUP, [userid, groupid])
            cursor.execute(Phpbb3Manager.SQL_CLEAR_USER_PERMISSIONS, [userid])
            logger.info("Removed phpbb user id %s from group id %s" % (userid, groupid))
        except:
            logger.exception("Unable to remove phpbb user id %s from group id %s" % (userid, groupid))
            pass

    @staticmethod
    def add_user(username, character_name, email, groups, characterid):
        logger.debug("Adding phpbb user with username %s, main character %s, email %s, groups %s, characterid %s" % (username, character_name, email, groups, characterid))
        cursor = connections['phpbb3'].cursor()

        username_clean = Phpbb3Manager.__clean_username(username)
        password = Phpbb3Manager.__generate_random_pass()
        pwhash = Phpbb3Manager.__gen_hash(password)
        logger.debug("Proceeding to add phpbb user %s and pwhash starting with %s" % (username_clean, pwhash[0:5]))
        # check if the username was simply revoked
        if Phpbb3Manager.check_character(character_name):
            if Phpbb3Manager.check_user(username_clean):
                if username_clean == Phpbb3Manager.__get_user_by_char(character_name):
                    logger.warn("The same pair username:character %s:%s already exists.  Updating instead." % (username_clean, character_name))
                    Phpbb3Manager.__update_user_info(username_clean, character_name, email, pwhash)
                else:
                    Phpbb3Manager.disable_user(username_clean, True)
                    Phpbb3Manager.__update_char_info(username_clean, character_name, email, pwhash)
            else:
                Phpbb3Manager.__update_char_info(username_clean, character_name, email, pwhash)
        else:
            if Phpbb3Manager.check_user(username_clean):
                logger.warn("Unable to add phpbb user with username %s - already exists. Updating user instead." % username_clean)
                Phpbb3Manager.__update_user_info(username_clean, character_name, email, pwhash)
            else:
                try:

                    cursor.execute(Phpbb3Manager.SQL_ADD_USER, [character_name, username_clean, pwhash, email, 2,
                                                                Phpbb3Manager.__get_current_utc_date(), "", ""])
                    Phpbb3Manager.update_groups(username_clean, groups)
                    Phpbb3Manager.__add_avatar(username_clean, characterid)
                    logger.info("Added phpbb user %s" % username_clean)
                except:
                    logger.exception("Unable to add phpbb user %s" % username_clean)
                    pass
        return username_clean, password

    @staticmethod
    def disable_user(username, change_username=False):
        logger.debug("Disabling phpbb user %s" % username)
        cursor = connections['phpbb3'].cursor()

        username_clean = Phpbb3Manager.__clean_username(username)
        password = Phpbb3Manager.__gen_hash(Phpbb3Manager.__generate_random_pass())
        if change_username:
            new_user = Phpbb3Manager.__generate_random_pass()
        else:
            new_user = username_clean
        revoke_email = "revoked@" + settings.DOMAIN
        try:
            pwhash = Phpbb3Manager.__gen_hash(password)
            userid = Phpbb3Manager.__get_user_id(username_clean)
            if userid:
                Phpbb3Manager.update_groups(username_clean, [])
                logger.debug("Disabling phpbb user %s using username %s" % (username_clean, new_user))
                cursor.execute(Phpbb3Manager.SQL_DIS_USER, [new_user, revoke_email, pwhash, username_clean])
                cursor.execute(Phpbb3Manager.SQL_DEL_AUTOLOGIN, [userid])
                cursor.execute(Phpbb3Manager.SQL_DEL_SESSION, [userid])
                logger.info("Disabled phpbb user %s" % username_clean)
                return True
            else:
                logger.warn("User %s not found while disabling." % username_clean)
                return True
        except TypeError as e:
            logger.exception("TypeError occured while disabling user %s - failed to disable." % username_clean)
            return False

    @staticmethod
    def update_groups(username, groups):
        username_clean = Phpbb3Manager.__clean_username(username)
        userid = Phpbb3Manager.__get_user_id(username_clean)
        logger.debug("Updating phpbb user %s with id %s groups %s" % (username_clean, userid, groups))
        if userid is not None:
            forum_groups = Phpbb3Manager.__get_all_groups()
            user_groups = set(Phpbb3Manager.__get_user_groups(userid))
            act_groups = set([g.replace(' ', '-') for g in groups])
            addgroups = act_groups - user_groups
            remgroups = user_groups - act_groups
            logger.info("Updating phpbb user %s groups - adding %s, removing %s" % (username_clean, addgroups, remgroups))
            for g in addgroups:
                if not g in forum_groups:
                    forum_groups[g] = Phpbb3Manager.__create_group(g)
                Phpbb3Manager.__add_user_to_group(userid, forum_groups[g])

            for g in remgroups:
                Phpbb3Manager.__remove_user_from_group(userid, forum_groups[g])

    @staticmethod
    def remove_group(username, group):
        logger.debug("Removing phpbb user %s from group %s" % (username, group))
        cursor = connections['phpbb3'].cursor()
        userid = Phpbb3Manager.__get_user_id(username)
        if userid is not None:
            groupid = Phpbb3Manager.__get_group_id(group)

            if userid:
                if groupid:
                    try:
                        cursor.execute(Phpbb3Manager.SQL_REMOVE_USER_GROUP, [userid, groupid])
                        logger.info("Removed phpbb user %s from group %s" % (username, group))
                    except:
                        logger.exception("Exception prevented removal of phpbb user %s with id %s from group %s with id %s" % (username, userid, group, groupid))
                        pass

    @staticmethod
    def check_character(character):
        logger.debug("Checking phpbb character %s" % character)
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_USER_FROM_CHARACTER, [character])
        row = cursor.fetchone()
        if row:
            logger.debug("Found character %s on phpbb" % character)
            return True
        logger.debug("Character %s not found on phpbb" % character)
        return False

    @staticmethod
    def check_user(username_clean):
        logger.debug("Checking phpbb user %s" % username_clean)
        cursor = connections['phpbb3'].cursor()
        cursor.execute(Phpbb3Manager.SQL_USER_ID_FROM_USERNAME, [username_clean])
        row = cursor.fetchone()
        if row:
            logger.debug("Found user %s on phpbb" % username_clean)
            return True
        logger.debug("User %s not found on phpbb" % username_clean)
        return False

    @staticmethod
    def update_user_main_char(username, character_name, characterid, email, password):
        username_clean = Phpbb3Manager.__clean_username(username)
        pwhash = Phpbb3Manager.__gen_hash(password)
        if Phpbb3Manager.check_character(character_name):
            username_old = Phpbb3Manager.__get_user_by_char(character_name)
            if username_old != username_clean:
                if Phpbb3Manager.check_user(username_clean):
                    Phpbb3Manager.disable_user(username_clean, True)
                Phpbb3Manager.disable_user(username_old, True)
                Phpbb3Manager.__update_char_info(username_clean, character_name, email, pwhash)
                Phpbb3Manager.__add_avatar(username_clean, characterid)
        else:
            cursor = connections['phpbb3'].cursor()
            try:
                cursor.execute(Phpbb3Manager.SQL_UPD_CHAR, [character_name, username_clean])
                logger.info("Updated phpbb user %s main character to %s" % (username_clean, character_name))
                Phpbb3Manager.__add_avatar(username_clean, characterid)
            except:
                logger.exception("Unable to update phpbb user %s main character to %s" % (username_clean, character_name))
                pass


    @staticmethod
    def update_user_password(username, characterid, password=None):
        username_clean = Phpbb3Manager.__clean_username(username)
        logger.debug("Updating phpbb user %s password" % username_clean)
        cursor = connections['phpbb3'].cursor()
        if not password:
            password = Phpbb3Manager.__generate_random_pass()
        if Phpbb3Manager.check_user(username_clean):
            pwhash = Phpbb3Manager.__gen_hash(password)
            logger.debug("Proceeding to update phpbb user %s password with pwhash starting with %s" % (username_clean, pwhash[0:5]))
            cursor.execute(Phpbb3Manager.SQL_UPDATE_USER_PASSWORD, [pwhash, username_clean])
            Phpbb3Manager.__add_avatar(username_clean, characterid)
            logger.info("Updated phpbb user %s password." % username_clean)
            return password
        logger.error("Unable to update phpbb user %s password - user not found on phpbb." % username_clean)
        return ""

    @staticmethod
    def __update_user_info(username_clean, character_name, email, password):
        logger.debug("Updating phpbb info based on user %s: character %s, email %s, password of length %s" % (username_clean, character_name, email, len(password)))
        cursor = connections['phpbb3'].cursor()
        try:
            cursor.execute(Phpbb3Manager.SQL_UPD_USER, [email, password, character_name, username_clean])
            logger.info("Updated phpbb user %s info" % username_clean)
        except:
            logger.exception("Unable to update phpbb user %s info." % username_clean)
            pass

    @staticmethod
    def __update_char_info(username_clean, character_name, email, password):
        logger.debug("Updating phpbb info based on character %s: user %s, email %s, password of length %s" % (character_name, username_clean, email, len(password)))
        cursor = connections['phpbb3'].cursor()
        try:
            cursor.execute(Phpbb3Manager.SQL_UPD_USER_BY_CHAR, [email, password, username_clean, character_name])
            logger.info("Updated phpbb user %s info" % username_clean)
        except:
            logger.exception("Unable to update phpbb user %s info." % username_clean)
            pass