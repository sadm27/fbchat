# -*- coding: UTF-8 -*-

from __future__ import unicode_literals
import requests
import urllib
from ._fetch import Fetcher
from uuid import uuid1
from random import choice
from bs4 import BeautifulSoup as bs
from mimetypes import guess_type
from collections import OrderedDict
from ._util import *
from .models import *
from .graphql import *
from ._send import Sender
import time

try:
    from urllib.parse import urlparse, parse_qs
except ImportError:
    from urlparse import urlparse, parse_qs


class Client(object):
    """A client for the Facebook Chat (Messenger).

    See https://fbchat.readthedocs.io for complete documentation of the API.
    """

    ssl_verify = True
    """Verify ssl certificate, set to False to allow debugging with a proxy"""
    listening = False
    """Whether the client is listening. Used when creating an external event loop to determine when to stop listening"""
    uid = None
    """
    The ID of the client.
    Can be used as `thread_id`. See :ref:`intro_threads` for more info.

    Note: Modifying this results in undefined behaviour
    """

    def __init__(
            self,
            email,
            password,
            user_agent=None,
            max_tries=5,
            session_cookies=None,
            logging_level=logging.INFO,
    ):
        """Initializes and logs in the client

        :param email: Facebook `email`, `id` or `phone number`
        :param password: Facebook account password
        :param user_agent: Custom user agent to use when sending requests. If `None`, user agent will be chosen from a premade list (see :any:`utils.USER_AGENTS`)
        :param max_tries: Maximum number of times to try logging in
        :param session_cookies: Cookies from a previous session (Will default to login if these are invalid)
        :param logging_level: Configures the `logging level <https://docs.python.org/3/library/logging.html#logging-levels>`_. Defaults to `INFO`
        :type max_tries: int
        :type session_cookies: dict
        :type logging_level: int
        :raises: FBchatException on failed login
        """

        self.sticky, self.pool = (None, None)
        self._session = requests.session()
        self.req_counter = 1
        self.seq = "0"
        # See `createPoll` for the reason for using `OrderedDict` here
        self.payloadDefault = OrderedDict()
        self.client = "mercury"
        self.default_thread_id = None
        self.default_thread_type = None
        self.req_url = ReqUrl()
        self._markAlive = True
        self._buddylist = dict()

        self.DaFetch = Fetcher(4)
        self.Sender = Sender()

        if not user_agent:
            user_agent = choice(USER_AGENTS)

        self._header = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": self.req_url.BASE,
            "Origin": self.req_url.BASE,
            "User-Agent": user_agent,
            "Connection": "keep-alive",
        }

        handler.setLevel(logging_level)

        # If session cookies aren't set, not properly loaded or gives us an invalid session, then do the login
        if (
                not session_cookies
                or not self.setSession(session_cookies)
                or not self.isLoggedIn()
        ):
            self.login(email, password, max_tries)
        else:
            self.email = email
            self.password = password

    """
    INTERNAL REQUEST METHODS
    """

    def _generatePayload(self, query):
        """Adds the following defaults to the payload:
          __rev, __user, __a, ttstamp, fb_dtsg, __req
        """
        payload = self.payloadDefault.copy()
        if query:
            payload.update(query)
        payload["__req"] = str_base(self.req_counter, 36)
        payload["seq"] = self.seq
        self.req_counter += 1
        return payload

    def _fix_fb_errors(self, error_code):
        """
        This fixes "Please try closing and re-opening your browser window" errors (1357004)
        This error usually happens after 1-2 days of inactivity
        It may be a bad idea to do this in an exception handler, if you have a better method, please suggest it!
        """
        if error_code == "1357004":
            log.warning("Got error #1357004. Doing a _postLogin, and resending request")
            self._postLogin()
            return True
        return False

    def _get(
            self,
            url,
            query=None,
            timeout=30,
            fix_request=False,
            as_json=False,
            error_retries=3,
    ):
        payload = self._generatePayload(query)
        r = self._session.get(
            url,
            headers=self._header,
            params=payload,
            timeout=timeout,
            verify=self.ssl_verify,
        )
        if not fix_request:
            return r
        try:
            return check_request(r, as_json=as_json)
        except FBchatFacebookError as e:
            if error_retries > 0 and self._fix_fb_errors(e.fb_error_code):
                return self._get(
                    url,
                    query=query,
                    timeout=timeout,
                    fix_request=fix_request,
                    as_json=as_json,
                    error_retries=error_retries - 1,
                )
            raise e

    def _post(
            self,
            url,
            query=None,
            timeout=30,
            fix_request=False,
            as_json=False,
            error_retries=3,
    ):
        payload = self._generatePayload(query)
        r = self._session.post(
            url,
            headers=self._header,
            data=payload,
            timeout=timeout,
            verify=self.ssl_verify,
        )
        if not fix_request:
            return r
        try:
            return check_request(r, as_json=as_json)
        except FBchatFacebookError as e:
            if error_retries > 0 and self._fix_fb_errors(e.fb_error_code):
                return self._post(
                    url,
                    query=query,
                    timeout=timeout,
                    fix_request=fix_request,
                    as_json=as_json,
                    error_retries=error_retries - 1,
                )
            raise e

    def _graphql(self, payload, error_retries=3):
        content = self._post(
            self.req_url.GRAPHQL, payload, fix_request=True, as_json=False
        )
        try:
            return graphql_response_to_json(content)
        except FBchatFacebookError as e:
            if error_retries > 0 and self._fix_fb_errors(e.fb_error_code):
                return self._graphql(payload, error_retries=error_retries - 1)
            raise e

    def _cleanGet(self, url, query=None, timeout=30, allow_redirects=True):
        return self._session.get(
            url,
            headers=self._header,
            params=query,
            timeout=timeout,
            verify=self.ssl_verify,
            allow_redirects=allow_redirects,
        )

    def _cleanPost(self, url, query=None, timeout=30):
        self.req_counter += 1
        return self._session.post(
            url,
            headers=self._header,
            data=query,
            timeout=timeout,
            verify=self.ssl_verify,
        )

    def _postFile(
            self,
            url,
            files=None,
            query=None,
            timeout=30,
            fix_request=False,
            as_json=False,
            error_retries=3,
    ):
        payload = self._generatePayload(query)
        # Removes 'Content-Type' from the header
        headers = dict(
            (i, self._header[i]) for i in self._header if i != "Content-Type"
        )
        r = self._session.post(
            url,
            headers=headers,
            data=payload,
            timeout=timeout,
            files=files,
            verify=self.ssl_verify,
        )
        if not fix_request:
            return r
        try:
            return check_request(r, as_json=as_json)
        except FBchatFacebookError as e:
            if error_retries > 0 and self._fix_fb_errors(e.fb_error_code):
                return self._postFile(
                    url,
                    files=files,
                    query=query,
                    timeout=timeout,
                    fix_request=fix_request,
                    as_json=as_json,
                    error_retries=error_retries - 1,
                )
            raise e

    def graphql_requests(self, *queries):
        """
        :param queries: Zero or more GraphQL objects
        :type queries: GraphQL

        :raises: FBchatException if request failed
        :return: A tuple containing json graphql queries
        :rtype: tuple
        """

        return tuple(
            self._graphql(
                {
                    "method": "GET",
                    "response_format": "json",
                    "queries": graphql_queries_to_json(*queries),
                }
            )
        )

    def graphql_request(self, query):
        """
        Shorthand for `graphql_requests(query)[0]`

        :raises: FBchatException if request failed
        """
        return self.graphql_requests(query)[0]

    """
    END INTERNAL REQUEST METHODS
    """

    """
    LOGIN METHODS
    """

    def _resetValues(self):
        self.payloadDefault = OrderedDict()
        self._session = requests.session()
        self.req_counter = 1
        self.seq = "0"
        self.uid = None

    def _postLogin(self):
        self.payloadDefault = OrderedDict()
        self.client_id = hex(int(random() * 2147483648))[2:]
        self.start_time = now()
        self.uid = self._session.cookies.get_dict().get("c_user")
        if self.uid is None:
            raise FBchatException("Could not find c_user cookie")
        self.uid = str(self.uid)
        self.user_channel = "p_" + self.uid
        self.ttstamp = ""

        r = self._get(self.req_url.BASE)
        soup = bs(r.text, "html.parser")

        fb_dtsg_element = soup.find("input", {"name": "fb_dtsg"})
        if fb_dtsg_element:
            self.fb_dtsg = fb_dtsg_element["value"]
        else:
            self.fb_dtsg = re.search(r'name="fb_dtsg" value="(.*?)"', r.text).group(1)

        fb_h_element = soup.find("input", {"name": "h"})
        if fb_h_element:
            self.fb_h = fb_h_element["value"]

        for i in self.fb_dtsg:
            self.ttstamp += str(ord(i))
        self.ttstamp += "2"
        # Set default payload
        self.payloadDefault["__rev"] = int(
            r.text.split('"client_revision":', 1)[1].split(",", 1)[0]
        )
        self.payloadDefault["__user"] = self.uid
        self.payloadDefault["__a"] = "1"
        self.payloadDefault["ttstamp"] = self.ttstamp
        self.payloadDefault["fb_dtsg"] = self.fb_dtsg

    def _login(self):
        if not (self.email and self.password):
            raise FBchatUserError("Email and password not found.")

        soup = bs(self._get(self.req_url.MOBILE).text, "html.parser")
        data = dict(
            (elem["name"], elem["value"])
            for elem in soup.findAll("input")
            if elem.has_attr("value") and elem.has_attr("name")
        )
        data["email"] = self.email
        data["pass"] = self.password
        data["login"] = "Log In"

        r = self._cleanPost(self.req_url.LOGIN, data)

        # Usually, 'Checkpoint' will refer to 2FA
        if "checkpoint" in r.url and ('id="approvals_code"' in r.text.lower()):
            r = self._2FA(r)

        # Sometimes Facebook tries to show the user a "Save Device" dialog
        if "save-device" in r.url:
            r = self._cleanGet(self.req_url.SAVE_DEVICE)

        if "home" in r.url:
            self._postLogin()
            return True, r.url
        else:
            return False, r.url

    def _2FA(self, r):
        soup = bs(r.text, "html.parser")
        data = dict()

        s = self.on2FACode()

        data["approvals_code"] = s
        data["fb_dtsg"] = soup.find("input", {"name": "fb_dtsg"})["value"]
        data["nh"] = soup.find("input", {"name": "nh"})["value"]
        data["submit[Submit Code]"] = "Submit Code"
        data["codes_submitted"] = 0
        log.info("Submitting 2FA code.")

        r = self._cleanPost(self.req_url.CHECKPOINT, data)

        if "home" in r.url:
            return r

        del (data["approvals_code"])
        del (data["submit[Submit Code]"])
        del (data["codes_submitted"])

        data["name_action_selected"] = "save_device"
        data["submit[Continue]"] = "Continue"
        log.info(
            "Saving browser."
        )  # At this stage, we have dtsg, nh, name_action_selected, submit[Continue]
        r = self._cleanPost(self.req_url.CHECKPOINT, data)

        if "home" in r.url:
            return r

        del (data["name_action_selected"])
        log.info(
            "Starting Facebook checkup flow."
        )  # At this stage, we have dtsg, nh, submit[Continue]
        r = self._cleanPost(self.req_url.CHECKPOINT, data)

        if "home" in r.url:
            return r

        del (data["submit[Continue]"])
        data["submit[This was me]"] = "This Was Me"
        log.info(
            "Verifying login attempt."
        )  # At this stage, we have dtsg, nh, submit[This was me]
        r = self._cleanPost(self.req_url.CHECKPOINT, data)

        if "home" in r.url:
            return r

        del (data["submit[This was me]"])
        data["submit[Continue]"] = "Continue"
        data["name_action_selected"] = "save_device"
        log.info(
            "Saving device again."
        )  # At this stage, we have dtsg, nh, submit[Continue], name_action_selected
        r = self._cleanPost(self.req_url.CHECKPOINT, data)
        return r

    def isLoggedIn(self):
        """
        Sends a request to Facebook to check the login status

        :return: True if the client is still logged in
        :rtype: bool
        """
        # Send a request to the login url, to see if we're directed to the home page
        r = self._cleanGet(self.req_url.LOGIN, allow_redirects=False)
        return "Location" in r.headers and "home" in r.headers["Location"]

    def getSession(self):
        """Retrieves session cookies

        :return: A dictionay containing session cookies
        :rtype: dict
        """
        return self._session.cookies.get_dict()

    def setSession(self, session_cookies):
        """Loads session cookies

        :param session_cookies: A dictionay containing session cookies
        :type session_cookies: dict
        :return: False if `session_cookies` does not contain proper cookies
        :rtype: bool
        """

        # Quick check to see if session_cookies is formatted properly
        if not session_cookies or "c_user" not in session_cookies:
            return False

        try:
            # Load cookies into current session
            self._session.cookies = requests.cookies.merge_cookies(
                self._session.cookies, session_cookies
            )
            self._postLogin()
        except Exception as e:
            log.exception("Failed loading session")
            self._resetValues()
            return False
        return True

    def login(self, email, password, max_tries=5):
        """
        Uses `email` and `password` to login the user (If the user is already logged in, this will do a re-login)

        :param email: Facebook `email` or `id` or `phone number`
        :param password: Facebook account password
        :param max_tries: Maximum number of times to try logging in
        :type max_tries: int
        :raises: FBchatException on failed login
        """
        self.onLoggingIn(email=email)

        if max_tries < 1:
            raise FBchatUserError("Cannot login: max_tries should be at least one")

        if not (email and password):
            raise FBchatUserError("Email and password not set")

        self.email = email
        self.password = password

        for i in range(1, max_tries + 1):
            login_successful, login_url = self._login()
            if not login_successful:
                log.warning(
                    "Attempt #{} failed{}".format(
                        i, {True: ", retrying"}.get(i < max_tries, "")
                    )
                )
                time.sleep(1)
                continue
            else:
                self.onLoggedIn(email=email)
                break
        else:
            raise FBchatUserError(
                "Login failed. Check email/password. (Failed on url: {})".format(
                    login_url
                )
            )

    def logout(self):
        """
        Safely logs out the client

        :param timeout: See `requests timeout <http://docs.python-requests.org/en/master/user/advanced/#timeouts>`_
        :return: True if the action was successful
        :rtype: bool
        """

        if not hasattr(self, "fb_h"):
            h_r = self._post(self.req_url.MODERN_SETTINGS_MENU, {"pmid": "4"})
            self.fb_h = re.search(r'name=\\"h\\" value=\\"(.*?)\\"', h_r.text).group(1)

        data = {"ref": "mb", "h": self.fb_h}

        r = self._get(self.req_url.LOGOUT, data)

        self._resetValues()

        return r.ok

    """
    END LOGIN METHODS
    """

    """
    DEFAULT THREAD METHODS
    """

    def _getThread(self, given_thread_id=None, given_thread_type=None):
        """
        Checks if thread ID is given, checks if default is set and returns correct values

        :raises ValueError: If thread ID is not given and there is no default
        :return: Thread ID and thread type
        :rtype: tuple
        """
        if given_thread_id is None:
            if self.default_thread_id is not None:
                return self.default_thread_id, self.default_thread_type
            else:
                raise ValueError("Thread ID is not set")
        else:
            return given_thread_id, given_thread_type

    def setDefaultThread(self, thread_id, thread_type):
        """
        Sets default thread to send messages to

        :param thread_id: User/Group ID to default to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        """
        self.default_thread_id = thread_id
        self.default_thread_type = thread_type

    def resetDefaultThread(self):
        """Resets default thread"""
        self.setDefaultThread(None, None)

    """
    END DEFAULT THREAD METHODS
    """


    """
    FETCH METHODS Callers
    """

    """
    Refactored all of the fetch functions my moveing them to _fetch.py

    :functions in client.py calls the original refactored functions in _fetch.py
    :an instance of the current client is sent to the fetcher along with the original arguments
    :this is down so whenever self was originally called it now uses client
    :Names for original functions are kept the same so changes are not seen on the surface
    """


    def _forcedFetch(self, thread_id, mid):
        return self.DaFetch.FET__forcedFetch(self, thread_id, mid)

    def fetchThreads(self, thread_location, before=None, after=None, limit=None):
        return self.DaFetch.FET_fetchThreads(self, thread_location, before, after, limit)

    def fetchAllUsersFromThreads(self, threads):
        return self.DaFetch.FET_fetchAllUsersFromThreads(self, threads)

    def fetchAllUsers(self):
        return self.DaFetch.FET_fetchAllUsers(self)

    def searchForUsers(self, name, limit=10):
        return self.DaFetch.FET_searchForUsers(self, name, limit)

    def searchForPages(self, name, limit=10):
        return self.DaFetch.FET_searchForPages(self, name, limit)

    def searchForGroups(self, name, limit=10):
        return self.DaFetch.FET_searchForGroups(self, name, limit)

    def searchForThreads(self, name, limit=10):
        return self.DaFetch.FET_searchForThreads(self, name, limit)

    def searchForMessageIDs(self, query, offset=0, limit=5, thread_id=None):
        return self.DaFetch.FET_searchForMessageIDs(self, query, offset, limit, thread_id)

    def searchForMessages(self, query, offset=0, limit=5, thread_id=None):
        return self.DaFetch.FET_searchForMessages(self, query, offset, limit, thread_id)

    def search(self, query, fetch_messages=False, thread_limit=5, message_limit=5):
        return self.DaFetch.FET_search(self, query, fetch_messages, thread_limit, message_limit)

    def _fetchInfo(self, *ids):
        return self.DaFetch.FET__fetchInfo(self, *ids)

    def fetchUserInfo(self, *user_ids):
        return self.DaFetch.FET_fetchUserInfo(self, *user_ids)

    def fetchPageInfo(self, *page_ids):
        return self.DaFetch.FET_fetchPageInfo(self, *page_ids)

    def fetchGroupInfo(self, *group_ids):
        return self.DaFetch.FET_fetchGroupInfo(self, *group_ids)

    def fetchThreadInfo(self, *thread_ids):
        return self.DaFetch.FET_fetchThreadInfo(self, *thread_ids)

    def fetchThreadMessages(self, thread_id=None, limit=20, before=None):
        return self.DaFetch.FET_fetchThreadMessages(self, thread_id, limit, before)

    def fetchUnreadFromThreadMessages(self, thread_id=None):
        #gets all the unread messages from the Client and prints their messages on screen in order to view it
        return self.DaFetch.FET_fetchUnreadFromThreadMessages(self, thread_id)

    def fetchThreadList(self, offset=None, limit=20, thread_location=ThreadLocation.INBOX, before=None):
        return self.DaFetch.FET_fetchThreadList(self, offset, limit, thread_location, before)

    def fetchUnread(self):
        return self.DaFetch.FET_fetchUnread(self)

    def fetchUnseen(self):
        return self.DaFetch.FET_fetchUnseen(self)


    def fetchImageUrl(self, image_id):
        return self.DaFetch.FET_fetchImageUrl(self, image_id)

    def fetchVideoUrl(self, video_id):
        return self.DaFetch.FET_fetchVideoUrl(self, video_id)

    def fetchJSON(self, attach_id):
        return self.DaFetch.FET_fetchJSON(self, attach_id)


    def fetchMessageInfo(self, mid, thread_id=None):
        return self.DaFetch.FET_fetchMessageInfo(self, mid, thread_id)

    def fetchPollOptions(self, poll_id):
        return self.DaFetch.FET_fetchPollOptions(self, poll_id)

    def fetchPlanInfo(self, plan_id):
        return self.DaFetch.FET_fetchPlanInfo(self, plan_id)

    def _getPrivateData(self):
        return self.DaFetch.FET__getPrivateData(self)

    def getPhoneNumbers(self):
        return self.DaFetch.FET_getPhoneNumbers(self)

    def getEmails(self):
        return self.DaFetch.FET_getEmails(self)

    def getUserActiveStatus(self, user_id):
        return self.DaFetch.FET_getUserActiveStatus(self, user_id)

    def getFromUserUrl(self, theUserUrl):
        return self.DaFetch.FET_getFromUserUrl(self, theUserUrl)

    def getFromGroupUrl(self, theGroupUrl):
        return self.DaFetch.FET_getFromGroupUrl(self, theGroupUrl)

    """
    END FETCH METHODS Callers
    """


    """
    SEND METHODS
    """

    def send(self, message, thread_id=None, thread_type=ThreadType.USER):
        """
        Sends a message to a thread

        :param message: Message to send
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type message: models.Message
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent message
        :raises: FBchatException if request failed
        """
        return Sender.s_send(self, message, thread_id, thread_type)

    def sendMessage(self, message, thread_id=None, thread_type=ThreadType.USER):
        """
        Deprecated. Use :func:`fbchat.Client.send` instead
        """
        return self.send(
            Message(text=message), thread_id=thread_id, thread_type=thread_type
        )

    def sendEmoji(self, emoji=None, size=EmojiSize.SMALL, thread_id=None, thread_type=ThreadType.USER,):
        """
        Deprecated. Use :func:`fbchat.Client.send` instead
        """
        return self.send(
            Message(text=emoji, emoji_size=size),
            thread_id=thread_id,
            thread_type=thread_type,
        )

    def wave(self, wave_first=True, thread_id=None, thread_type=None):
        """
        Says hello with a wave to a thread!

        :param wave_first: Whether to wave first or wave back
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent message
        :raises: FBchatException if request failed
        """
        return Sender.s_wave(self.Sender, self, wave_first, thread_id, thread_type)

    def quickReply(self, quick_reply, payload=None, thread_id=None, thread_type=None):
        """
        Replies to a chosen quick reply

        :param quick_reply: Quick reply to reply to
        :param payload: Optional answer to the quick reply
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type quick_reply: models.QuickReply
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent message
        :raises: FBchatException if request failed
        """
        return Sender.s_quick_reply(self.Sender, self, quick_reply, payload, thread_id, thread_type)

    def unsend(self, mid):
        """
        Unsends a message (removes for everyone)

        :param mid: :ref:`Message ID <intro_message_ids>` of the message to unsend
        """
        Sender.s_unsend(self.Sender, self, mid)

    def sendLocation(self, location, thread_id=None, thread_type=None):
        """
        Sends a given location to a thread as the user's current location

        :param location: Location to send
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type location: models.LocationAttachment
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent message
        :raises: FBchatException if request failed
        """
        Sender.s_send_location(self.Sender, self, location, thread_id, thread_type)

    def sendPinnedLocation(self, location, thread_id=None, thread_type=None):
        """
        Sends a given location to a thread as a pinned location

        :param location: Location to send
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type location: models.LocationAttachment
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent message
        :raises: FBchatException if request failed
        """
        Sender.s_send_pinned_location(self.Sender, self, location, thread_id, thread_type)

    def sendRemoteFiles(self, file_urls, message=None, thread_id=None, thread_type=ThreadType.USER):
        """
        Sends files from URLs to a thread

        :param file_urls: URLs of files to upload and send
        :param message: Additional message
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent files
        :raises: FBchatException if request failed
        """
        return Sender.s_send_remote_files(self.Sender, self, file_urls, message, thread_id, thread_type)

    def sendLocalFiles(self, file_paths, message=None, thread_id=None, thread_type=ThreadType.USER):
        """
        Sends local files to a thread

        :param file_paths: Paths of files to upload and send
        :param message: Additional message
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent files
        :raises: FBchatException if request failed
        """
        return Sender.s_send_local_files(self.Sender, self, file_paths, message, thread_id, thread_type)

    def sendRemoteVoiceClips(self, clip_urls, message=None, thread_id=None, thread_type=ThreadType.USER):
        """
        Sends voice clips from URLs to a thread

        :param clip_urls: URLs of clips to upload and send
        :param message: Additional message
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent files
        :raises: FBchatException if request failed
        """
        return Sender.s_send_remote_voice_clips(self.Sender, self, clip_urls, message, thread_id, thread_type)

    def sendLocalVoiceClips(self, clip_paths, message=None, thread_id=None, thread_type=ThreadType.USER):
        """
        Sends local voice clips to a thread

        :param clip_paths: Paths of clips to upload and send
        :param message: Additional message
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent files
        :raises: FBchatException if request failed
        """
        return Sender.s_send_local_voice_clips(self.Sender, self, clip_paths, message, thread_id, thread_type)

    def sendImage(self, image_id, message=None, thread_id=None, thread_type=ThreadType.USER, is_gif=False,):
        """
        Deprecated. Use :func:`fbchat.Send._sendFiles` instead
        """
        return Sender.s_send_image(self.Sender, self, image_id, message, thread_id, thread_type, is_gif)

    def sendRemoteImage(self, image_url, message=None, thread_id=None, thread_type=ThreadType.USER):
        """
        Deprecated. Use :func:`fbchat.Client.sendRemoteFiles` instead
        """
        return Sender.s_send_remote_image(self.Sender, self, image_url, message, thread_id, thread_type)

    def sendLocalImage(self, image_path, message=None, thread_id=None, thread_type=ThreadType.USER):
        """
        Deprecated. Use :func:`fbchat.Client.sendLocalFiles` instead
        """
        return Sender.s_send_local_image(self.Sender, self, image_path, message, thread_id, thread_type)

    def createGroup(self, message, user_ids):
        """
        Creates a group with the given ids

        :param message: The initial message
        :param user_ids: A list of users to create the group with.
        :return: ID of the new group
        :raises: FBchatException if request failed
        """
        return Sender.s_create_group(self.Sender, self, message, user_ids)

    def addUsersToGroup(self, user_ids, thread_id=None):
        """
        Adds users to a group.

        :param user_ids: One or more user IDs to add
        :param thread_id: Group ID to add people to. See :ref:`intro_threads`
        :type user_ids: list
        :raises: FBchatException if request failed
        """
        return Sender.s_add_users_to_group(self.Sender, self, user_ids, thread_id)

    def removeUserFromGroup(self, user_id, thread_id=None):
        """
        Removes users from a group.

        :param user_id: User ID to remove
        :param thread_id: Group ID to remove people from. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        Sender.s_remove_user_from_group(self.Sender, self, user_id, thread_id)

    def addGroupAdmins(self, admin_ids, thread_id=None):
        """
        Sets specifed users as group admins.

        :param admin_ids: One or more user IDs to set admin
        :param thread_id: Group ID to remove people from. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        Sender.s_add_group_admins(self.Sender, self, admin_ids, thread_id)

    def removeGroupAdmins(self, admin_ids, thread_id=None):
        """
        Removes admin status from specifed users.

        :param admin_ids: One or more user IDs to remove admin
        :param thread_id: Group ID to remove people from. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        Sender.s_remove_group_admins(self.Sender, self, admin_ids, thread_id)

    def changeGroupApprovalMode(self, require_admin_approval, thread_id=None):
        """
        Changes group's approval mode

        :param require_admin_approval: True or False
        :param thread_id: Group ID to remove people from. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        Sender.s_change_group_approval_mode(self.Sender, self, require_admin_approval, thread_id)

    def acceptUsersToGroup(self, user_ids, thread_id=None):
        """
        Accepts users to the group from the group's approval

        :param user_ids: One or more user IDs to accept
        :param thread_id: Group ID to accept users to. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        Sender.s_accept_users_to_group(self.Sender, self, user_ids, thread_id)

    def denyUsersFromGroup(self, user_ids, thread_id=None):
        """
        Denies users from the group's approval

        :param user_ids: One or more user IDs to deny
        :param thread_id: Group ID to deny users from. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        Sender.s_deny_users_from_group(self.Sender, self, user_ids, thread_id)

    def changeGroupImageRemote(self, image_url, thread_id=None):
        """
        Changes a thread image from a URL

        :param image_url: URL of an image to upload and change
        :param thread_id: User/Group ID to change image. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        return Sender.s_change_group_image_remote(self.Sender, self, image_url, thread_id)

    def changeGroupImageLocal(self, image_path, thread_id=None):
        """
        Changes a thread image from a local path

        :param image_path: Path of an image to upload and change
        :param thread_id: User/Group ID to change image. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        return Sender.s_change_group_image_local(self.Sender, self, image_path, thread_id)

    def changeThreadTitle(self, title, thread_id=None, thread_type=ThreadType.USER):
        """
        Changes title of a thread.
        If this is executed on a user thread, this will change the nickname of that user, effectively changing the title

        :param title: New group thread title
        :param thread_id: Group ID to change title of. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :raises: FBchatException if request failed
        """
        Sender.s_change_thread_title(self.Sender, self, title, thread_id, thread_type)

    def changeNickname(self, nickname, user_id, thread_id=None, thread_type=ThreadType.USER):
        """
        Changes the nickname of a user in a thread

        :param nickname: New nickname
        :param user_id: User that will have their nickname changed
        :param thread_id: User/Group ID to change color of. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :raises: FBchatException if request failed
        """
        Sender.s_change_nickname(self.Sender, self, nickname, user_id, thread_id, thread_type)

    def changeThreadColor(self, color, thread_id=None):
        """
        Changes thread color

        :param color: New thread color
        :param thread_id: User/Group ID to change color of. See :ref:`intro_threads`
        :type color: models.ThreadColor
        :raises: FBchatException if request failed
        """
        Sender.s_change_thread_color(self.Sender, self, color, thread_id)

    def changeThreadEmoji(self, emoji, thread_id=None):
        """
        Changes thread color

        Trivia: While changing the emoji, the Facebook web client actually sends multiple different requests, though only this one is required to make the change

        :param color: New thread emoji
        :param thread_id: User/Group ID to change emoji of. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        Sender.s_change_thread_emoji(self.Sender, self, emoji, thread_id)

    def reactToMessage(self, message_id, reaction):
        """
        Reacts to a message, or removes reaction

        :param message_id: :ref:`Message ID <intro_message_ids>` to react to
        :param reaction: Reaction emoji to use, if None removes reaction
        :type reaction: models.MessageReaction or None
        :raises: FBchatException if request failed
        """
        Sender.s_react_to_message(self.Sender, self, message_id, reaction)

    def createPlan(self, plan, thread_id=None):
        """
        Sets a plan

        :param plan: Plan to set
        :param thread_id: User/Group ID to send plan to. See :ref:`intro_threads`
        :type plan: models.Plan
        :raises: FBchatException if request failed
        """
        Sender.s_create_plan(self.Sender, self, plan, thread_id)

    def editPlan(self, plan, new_plan):
        """
        Edits a plan

        :param plan: Plan to edit
        :param new_plan: New plan
        :type plan: models.Plan
        :raises: FBchatException if request failed
        """
        Sender.s_edit_plan(self.Sender, self, plan, new_plan)

    def deletePlan(self, plan):
        """
        Deletes a plan

        :param plan: Plan to delete
        :raises: FBchatException if request failed
        """
        Sender.s_delete_plan(self.Sender, self, plan)

    def changePlanParticipation(self, plan, take_part=True):
        """
        Changes participation in a plan

        :param plan: Plan to take part in or not
        :param take_part: Whether to take part in the plan
        :raises: FBchatException if request failed
        """
        Sender.s_change_plan_participation(self.Sender, self, plan, take_part)

    def eventReminder(self, thread_id, time, title, location="", location_id=""):
        """
        Deprecated. Use :func:`fbchat.Client.createPlan` instead
        """
        Sender.s_event_reminder(self.Sender, self, thread_id, time, title, location, location_id)

    def createPoll(self, poll, thread_id=None):
        """
        Creates poll in a group thread

        :param poll: Poll to create
        :param thread_id: User/Group ID to create poll in. See :ref:`intro_threads`
        :type poll: models.Poll
        :raises: FBchatException if request failed
        """
        Sender.s_create_poll(self.Sender, self, poll, thread_id)

    def updatePollVote(self, poll_id, option_ids=[], new_options=[]):
        """
        Updates a poll vote

        :param poll_id: ID of the poll to update vote
        :param option_ids: List of the option IDs to vote
        :param new_options: List of the new option names
        :param thread_id: User/Group ID to change status in. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :raises: FBchatException if request failed
        """
        Sender.s_update_poll_vote(self.Sender, self, poll_id, option_ids, new_options)

    def setTypingStatus(self, status, thread_id=None, thread_type=None):
        """
        Sets users typing status in a thread

        :param status: Specify the typing status
        :param thread_id: User/Group ID to change status in. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type status: models.TypingStatus
        :type thread_type: models.ThreadType
        :raises: FBchatException if request failed
        """
        Sender.s_set_typing_status(self.Sender, self, status, thread_id, thread_type)

    """
    END SEND METHODS
    """

    def markAsDelivered(self, thread_id, message_id):
        """
        Mark a message as delivered

        :param thread_id: User/Group ID to which the message belongs. See :ref:`intro_threads`
        :param message_id: Message ID to set as delivered. See :ref:`intro_threads`
        :return: Whether the request was successful
        :raises: FBchatException if request failed
        """
        data = {
            "message_ids[0]": message_id,
            "thread_ids[%s][0]" % thread_id: message_id,
        }

        r = self._post(self.req_url.DELIVERED, data)
        return r.ok

    def _readStatus(self, read, thread_ids):
        thread_ids = require_list(thread_ids)

        data = {"watermarkTimestamp": now(), "shouldSendReadReceipt": "true"}

        for thread_id in thread_ids:
            data["ids[{}]".format(thread_id)] = "true" if read else "false"

        r = self._post(self.req_url.READ_STATUS, data)
        return r.ok

    def markAsRead(self, thread_ids=None):
        """
        Mark threads as read
        All messages inside the threads will be marked as read

        :param thread_ids: User/Group IDs to set as read. See :ref:`intro_threads`
        :return: Whether the request was successful
        :raises: FBchatException if request failed
        """
        self._readStatus(True, thread_ids)

    def markAsUnread(self, thread_ids=None):
        """
        Mark threads as unread
        All messages inside the threads will be marked as unread

        :param thread_ids: User/Group IDs to set as unread. See :ref:`intro_threads`
        :return: Whether the request was successful
        :raises: FBchatException if request failed
        """
        self._readStatus(False, thread_ids)

    def markAsSeen(self):
        """
        .. todo::
            Documenting this
        """
        r = self._post(self.req_url.MARK_SEEN, {"seen_timestamp": now()})
        return r.ok

    def friendConnect(self, friend_id):
        """
        .. todo::
            Documenting this
        """
        data = {"to_friend": friend_id, "action": "confirm"}

        r = self._post(self.req_url.CONNECT, data)
        return r.ok

    def removeFriend(self, friend_id=None):
        """
        Removes a specifed friend from your friend list

        :param friend_id: The ID of the friend that you want to remove
        :return: Returns error if the removing was unsuccessful, returns True when successful.
        """
        payload = {"friend_id": friend_id, "unref": "none", "confirm": "Confirm"}
        r = self._post(self.req_url.REMOVE_FRIEND, payload)
        query = parse_qs(urlparse(r.url).query)
        if "err" not in query:
            log.debug("Remove was successful!")
            return True
        else:
            log.warning("Error while removing friend")
            return False

    def blockUser(self, user_id):
        """
        Blocks messages from a specifed user

        :param user_id: The ID of the user that you want to block
        :return: Whether the request was successful
        :raises: FBchatException if request failed
        """
        data = {"fbid": user_id}
        r = self._post(self.req_url.BLOCK_USER, data)
        return r.ok

    def unblockUser(self, user_id):
        """
        Unblocks messages from a blocked user

        :param user_id: The ID of the user that you want to unblock
        :return: Whether the request was successful
        :raises: FBchatException if request failed
        """
        data = {"fbid": user_id}
        r = self._post(self.req_url.UNBLOCK_USER, data)
        return r.ok

    def moveThreads(self, location, thread_ids):
        """
        Moves threads to specifed location

        :param location: models.ThreadLocation: INBOX, PENDING, ARCHIVED or OTHER
        :param thread_ids: Thread IDs to move. See :ref:`intro_threads`
        :return: Whether the request was successful
        :raises: FBchatException if request failed
        """
        thread_ids = require_list(thread_ids)

        if location == ThreadLocation.PENDING:
            location = ThreadLocation.OTHER

        if location == ThreadLocation.ARCHIVED:
            data_archive = dict()
            data_unpin = dict()
            for thread_id in thread_ids:
                data_archive["ids[{}]".format(thread_id)] = "true"
                data_unpin["ids[{}]".format(thread_id)] = "false"
            r_archive = self._post(self.req_url.ARCHIVED_STATUS, data_archive)
            r_unpin = self._post(self.req_url.PINNED_STATUS, data_unpin)
            return r_archive.ok and r_unpin.ok
        else:
            data = dict()
            for i, thread_id in enumerate(thread_ids):
                data["{}[{}]".format(location.name.lower(), i)] = thread_id
            r = self._post(self.req_url.MOVE_THREAD, data)
            return r.ok

    def deleteThreads(self, thread_ids):
        """
        Deletes threads

        :param thread_ids: Thread IDs to delete. See :ref:`intro_threads`
        :return: Whether the request was successful
        :raises: FBchatException if request failed
        """
        thread_ids = require_list(thread_ids)

        data_unpin = dict()
        data_delete = dict()
        for i, thread_id in enumerate(thread_ids):
            data_unpin["ids[{}]".format(thread_id)] = "false"
            data_delete["ids[{}]".format(i)] = thread_id
        r_unpin = self._post(self.req_url.PINNED_STATUS, data_unpin)
        r_delete = self._post(self.req_url.DELETE_THREAD, data_delete)
        return r_unpin.ok and r_delete.ok

    def markAsSpam(self, thread_id=None):
        """
        Mark a thread as spam and delete it

        :param thread_id: User/Group ID to mark as spam. See :ref:`intro_threads`
        :return: Whether the request was successful
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = self._getThread(thread_id, None)
        r = self._post(self.req_url.MARK_SPAM, {"id": thread_id})
        return r.ok

    def deleteMessages(self, message_ids):
        """
        Deletes specifed messages

        :param message_ids: Message IDs to delete
        :return: Whether the request was successful
        :raises: FBchatException if request failed
        """
        message_ids = require_list(message_ids)
        data = dict()
        for i, message_id in enumerate(message_ids):
            data["message_ids[{}]".format(i)] = message_id
        r = self._post(self.req_url.DELETE_MESSAGES, data)
        return r.ok

    def muteThread(self, mute_time=-1, thread_id=None):
        """
        Mutes thread

        :param mute_time: Mute time in seconds, leave blank to mute forever
        :param thread_id: User/Group ID to mute. See :ref:`intro_threads`
        """
        thread_id, thread_type = self._getThread(thread_id, None)
        data = {"mute_settings": str(mute_time), "thread_fbid": thread_id}
        r = self._post(self.req_url.MUTE_THREAD, data)
        r.raise_for_status()

    def unmuteThread(self, thread_id=None):
        """
        Unmutes thread

        :param thread_id: User/Group ID to unmute. See :ref:`intro_threads`
        """
        return self.muteThread(0, thread_id)

    def muteThreadReactions(self, mute=True, thread_id=None):
        """
        Mutes thread reactions

        :param mute: Boolean. True to mute, False to unmute
        :param thread_id: User/Group ID to mute. See :ref:`intro_threads`
        """
        thread_id, thread_type = self._getThread(thread_id, None)
        data = {"reactions_mute_mode": int(mute), "thread_fbid": thread_id}
        r = self._post(self.req_url.MUTE_REACTIONS, data)
        r.raise_for_status()

    def unmuteThreadReactions(self, thread_id=None):
        """
        Unmutes thread reactions

        :param thread_id: User/Group ID to unmute. See :ref:`intro_threads`
        """
        return self.muteThreadReactions(False, thread_id)

    def muteThreadMentions(self, mute=True, thread_id=None):
        """
        Mutes thread mentions

        :param mute: Boolean. True to mute, False to unmute
        :param thread_id: User/Group ID to mute. See :ref:`intro_threads`
        """
        thread_id, thread_type = self._getThread(thread_id, None)
        data = {"mentions_mute_mode": int(mute), "thread_fbid": thread_id}
        r = self._post(self.req_url.MUTE_MENTIONS, data)
        r.raise_for_status()

    def unmuteThreadMentions(self, thread_id=None):
        """
        Unmutes thread mentions

        :param thread_id: User/Group ID to unmute. See :ref:`intro_threads`
        """
        return self.muteThreadMentions(False, thread_id)

    """
    LISTEN METHODS
    """

    def _ping(self):
        data = {
            "channel": self.user_channel,
            "clientid": self.client_id,
            "partition": -2,
            "cap": 0,
            "uid": self.uid,
            "sticky_token": self.sticky,
            "sticky_pool": self.pool,
            "viewer_uid": self.uid,
            "state": "active",
        }
        self._get(self.req_url.PING, data, fix_request=True, as_json=False)

    def _pullMessage(self):
        """Call pull api with seq value to get message data."""

        data = {
            "msgs_recv": 0,
            "sticky_token": self.sticky,
            "sticky_pool": self.pool,
            "clientid": self.client_id,
            "state": "active" if self._markAlive else "offline",
        }

        j = self._get(self.req_url.STICKY, data, fix_request=True, as_json=True)

        self.seq = j.get("seq", "0")
        return j

    def _parseDelta(self, m):
        def getThreadIdAndThreadType(msg_metadata):
            """Returns a tuple consisting of thread ID and thread type"""
            id_thread = None
            type_thread = None
            if "threadFbId" in msg_metadata["threadKey"]:
                id_thread = str(msg_metadata["threadKey"]["threadFbId"])
                type_thread = ThreadType.GROUP
            elif "otherUserFbId" in msg_metadata["threadKey"]:
                id_thread = str(msg_metadata["threadKey"]["otherUserFbId"])
                type_thread = ThreadType.USER
            return id_thread, type_thread

        delta = m["delta"]
        delta_type = delta.get("type")
        delta_class = delta.get("class")
        metadata = delta.get("messageMetadata")

        if metadata:
            mid = metadata["messageId"]
            author_id = str(metadata["actorFbId"])
            ts = int(metadata.get("timestamp"))

        # Added participants
        if "addedParticipants" in delta:
            added_ids = [str(x["userFbId"]) for x in delta["addedParticipants"]]
            thread_id = str(metadata["threadKey"]["threadFbId"])
            self.onPeopleAdded(
                mid=mid,
                added_ids=added_ids,
                author_id=author_id,
                thread_id=thread_id,
                ts=ts,
                msg=m,
            )

        # Left/removed participants
        elif "leftParticipantFbId" in delta:
            removed_id = str(delta["leftParticipantFbId"])
            thread_id = str(metadata["threadKey"]["threadFbId"])
            self.onPersonRemoved(
                mid=mid,
                removed_id=removed_id,
                author_id=author_id,
                thread_id=thread_id,
                ts=ts,
                msg=m,
            )

        # Color change
        elif delta_type == "change_thread_theme":
            new_color = graphql_color_to_enum(delta["untypedData"]["theme_color"])
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            self.onColorChange(
                mid=mid,
                author_id=author_id,
                new_color=new_color,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Emoji change
        elif delta_type == "change_thread_icon":
            new_emoji = delta["untypedData"]["thread_icon"]
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            self.onEmojiChange(
                mid=mid,
                author_id=author_id,
                new_emoji=new_emoji,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Thread title change
        elif delta_class == "ThreadName":
            new_title = delta["name"]
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            self.onTitleChange(
                mid=mid,
                author_id=author_id,
                new_title=new_title,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Forced fetch
        elif delta_class == "ForcedFetch":
            mid = delta.get("messageId")
            if mid is None:
                self.onUnknownMesssageType(msg=m)
            else:
                thread_id = str(delta["threadKey"]["threadFbId"])
                fetch_info = self._forcedFetch(thread_id, mid)
                fetch_data = fetch_info["message"]
                author_id = fetch_data["message_sender"]["id"]
                ts = fetch_data["timestamp_precise"]
                if fetch_data.get("__typename") == "ThreadImageMessage":
                    # Thread image change
                    image_metadata = fetch_data.get("image_with_metadata")
                    image_id = (
                        int(image_metadata["legacy_attachment_id"])
                        if image_metadata
                        else None
                    )
                    self.onImageChange(
                        mid=mid,
                        author_id=author_id,
                        new_image=image_id,
                        thread_id=thread_id,
                        thread_type=ThreadType.GROUP,
                        ts=ts,
                        msg=m,
                    )

        # Nickname change
        elif delta_type == "change_thread_nickname":
            changed_for = str(delta["untypedData"]["participant_id"])
            new_nickname = delta["untypedData"]["nickname"]
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            self.onNicknameChange(
                mid=mid,
                author_id=author_id,
                changed_for=changed_for,
                new_nickname=new_nickname,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Admin added or removed in a group thread
        elif delta_type == "change_thread_admins":
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            target_id = delta["untypedData"]["TARGET_ID"]
            admin_event = delta["untypedData"]["ADMIN_EVENT"]
            if admin_event == "add_admin":
                self.onAdminAdded(
                    mid=mid,
                    added_id=target_id,
                    author_id=author_id,
                    thread_id=thread_id,
                    thread_type=thread_type,
                    ts=ts,
                    msg=m,
                )
            elif admin_event == "remove_admin":
                self.onAdminRemoved(
                    mid=mid,
                    removed_id=target_id,
                    author_id=author_id,
                    thread_id=thread_id,
                    thread_type=thread_type,
                    ts=ts,
                    msg=m,
                )

        # Group approval mode change
        elif delta_type == "change_thread_approval_mode":
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            approval_mode = bool(int(delta["untypedData"]["APPROVAL_MODE"]))
            self.onApprovalModeChange(
                mid=mid,
                approval_mode=approval_mode,
                author_id=author_id,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                msg=m,
            )

        # Message delivered
        elif delta_class == "DeliveryReceipt":
            message_ids = delta["messageIds"]
            delivered_for = str(
                delta.get("actorFbId") or delta["threadKey"]["otherUserFbId"]
            )
            ts = int(delta["deliveredWatermarkTimestampMs"])
            thread_id, thread_type = getThreadIdAndThreadType(delta)
            self.onMessageDelivered(
                msg_ids=message_ids,
                delivered_for=delivered_for,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Message seen
        elif delta_class == "ReadReceipt":
            seen_by = str(delta.get("actorFbId") or delta["threadKey"]["otherUserFbId"])
            seen_ts = int(delta["actionTimestampMs"])
            delivered_ts = int(delta["watermarkTimestampMs"])
            thread_id, thread_type = getThreadIdAndThreadType(delta)
            self.onMessageSeen(
                seen_by=seen_by,
                thread_id=thread_id,
                thread_type=thread_type,
                seen_ts=seen_ts,
                ts=delivered_ts,
                metadata=metadata,
                msg=m,
            )

        # Messages marked as seen
        elif delta_class == "MarkRead":
            seen_ts = int(
                delta.get("actionTimestampMs") or delta.get("actionTimestamp")
            )
            delivered_ts = int(
                delta.get("watermarkTimestampMs") or delta.get("watermarkTimestamp")
            )

            threads = []
            if "folders" not in delta:
                threads = [
                    getThreadIdAndThreadType({"threadKey": thr})
                    for thr in delta.get("threadKeys")
                ]

            # thread_id, thread_type = getThreadIdAndThreadType(delta)
            self.onMarkedSeen(
                threads=threads, seen_ts=seen_ts, ts=delivered_ts, metadata=delta, msg=m
            )

        # Game played
        elif delta_type == "instant_game_update":
            game_id = delta["untypedData"]["game_id"]
            game_name = delta["untypedData"]["game_name"]
            score = delta["untypedData"].get("score")
            if score is not None:
                score = int(score)
            leaderboard = delta["untypedData"].get("leaderboard")
            if leaderboard is not None:
                leaderboard = json.loads(leaderboard)["scores"]
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            self.onGamePlayed(
                mid=mid,
                author_id=author_id,
                game_id=game_id,
                game_name=game_name,
                score=score,
                leaderboard=leaderboard,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Group call started/ended
        elif delta_type == "rtc_call_log":
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            call_status = delta["untypedData"]["event"]
            call_duration = int(delta["untypedData"]["call_duration"])
            is_video_call = bool(int(delta["untypedData"]["is_video_call"]))
            if call_status == "call_started":
                self.onCallStarted(
                    mid=mid,
                    caller_id=author_id,
                    is_video_call=is_video_call,
                    thread_id=thread_id,
                    thread_type=thread_type,
                    ts=ts,
                    metadata=metadata,
                    msg=m,
                )
            elif call_status == "call_ended":
                self.onCallEnded(
                    mid=mid,
                    caller_id=author_id,
                    is_video_call=is_video_call,
                    call_duration=call_duration,
                    thread_id=thread_id,
                    thread_type=thread_type,
                    ts=ts,
                    metadata=metadata,
                    msg=m,
                )

        # User joined to group call
        elif delta_type == "participant_joined_group_call":
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            is_video_call = bool(int(delta["untypedData"]["group_call_type"]))
            self.onUserJoinedCall(
                mid=mid,
                joined_id=author_id,
                is_video_call=is_video_call,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Group poll event
        elif delta_type == "group_poll":
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            event_type = delta["untypedData"]["event_type"]
            poll_json = json.loads(delta["untypedData"]["question_json"])
            poll = graphql_to_poll(poll_json)
            if event_type == "question_creation":
                # User created group poll
                self.onPollCreated(
                    mid=mid,
                    poll=poll,
                    author_id=author_id,
                    thread_id=thread_id,
                    thread_type=thread_type,
                    ts=ts,
                    metadata=metadata,
                    msg=m,
                )
            elif event_type == "update_vote":
                # User voted on group poll
                added_options = json.loads(delta["untypedData"]["added_option_ids"])
                removed_options = json.loads(delta["untypedData"]["removed_option_ids"])
                self.onPollVoted(
                    mid=mid,
                    poll=poll,
                    added_options=added_options,
                    removed_options=removed_options,
                    author_id=author_id,
                    thread_id=thread_id,
                    thread_type=thread_type,
                    ts=ts,
                    metadata=metadata,
                    msg=m,
                )

        # Plan created
        elif delta_type == "lightweight_event_create":
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            plan = graphql_to_plan(delta["untypedData"])
            self.onPlanCreated(
                mid=mid,
                plan=plan,
                author_id=author_id,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Plan ended
        elif delta_type == "lightweight_event_notify":
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            plan = graphql_to_plan(delta["untypedData"])
            self.onPlanEnded(
                mid=mid,
                plan=plan,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Plan edited
        elif delta_type == "lightweight_event_update":
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            plan = graphql_to_plan(delta["untypedData"])
            self.onPlanEdited(
                mid=mid,
                plan=plan,
                author_id=author_id,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Plan deleted
        elif delta_type == "lightweight_event_delete":
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            plan = graphql_to_plan(delta["untypedData"])
            self.onPlanDeleted(
                mid=mid,
                plan=plan,
                author_id=author_id,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Plan participation change
        elif delta_type == "lightweight_event_rsvp":
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            plan = graphql_to_plan(delta["untypedData"])
            take_part = delta["untypedData"]["guest_status"] == "GOING"
            self.onPlanParticipation(
                mid=mid,
                plan=plan,
                take_part=take_part,
                author_id=author_id,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Client payload (that weird numbers)
        elif delta_class == "ClientPayload":
            payload = json.loads("".join(chr(z) for z in delta["payload"]))
            ts = m.get("ofd_ts")
            for d in payload.get("deltas", []):

                # Message reaction
                if d.get("deltaMessageReaction"):
                    i = d["deltaMessageReaction"]
                    thread_id, thread_type = getThreadIdAndThreadType(i)
                    mid = i["messageId"]
                    author_id = str(i["userId"])
                    reaction = (
                        MessageReaction(i["reaction"]) if i.get("reaction") else None
                    )
                    add_reaction = not bool(i["action"])
                    if add_reaction:
                        self.onReactionAdded(
                            mid=mid,
                            reaction=reaction,
                            author_id=author_id,
                            thread_id=thread_id,
                            thread_type=thread_type,
                            ts=ts,
                            msg=m,
                        )
                    else:
                        self.onReactionRemoved(
                            mid=mid,
                            author_id=author_id,
                            thread_id=thread_id,
                            thread_type=thread_type,
                            ts=ts,
                            msg=m,
                        )

                # Viewer status change
                elif d.get("deltaChangeViewerStatus"):
                    i = d["deltaChangeViewerStatus"]
                    thread_id, thread_type = getThreadIdAndThreadType(i)
                    author_id = str(i["actorFbid"])
                    reason = i["reason"]
                    can_reply = i["canViewerReply"]
                    if reason == 2:
                        if can_reply:
                            self.onUnblock(
                                author_id=author_id,
                                thread_id=thread_id,
                                thread_type=thread_type,
                                ts=ts,
                                msg=m,
                            )
                        else:
                            self.onBlock(
                                author_id=author_id,
                                thread_id=thread_id,
                                thread_type=thread_type,
                                ts=ts,
                                msg=m,
                            )

                # Live location info
                elif d.get("liveLocationData"):
                    i = d["liveLocationData"]
                    thread_id, thread_type = getThreadIdAndThreadType(i)
                    for l in i["messageLiveLocations"]:
                        mid = l["messageId"]
                        author_id = str(l["senderId"])
                        location = graphql_to_live_location(l)
                        self.onLiveLocation(
                            mid=mid,
                            location=location,
                            author_id=author_id,
                            thread_id=thread_id,
                            thread_type=thread_type,
                            ts=ts,
                            msg=m,
                        )

                # Message deletion
                elif d.get("deltaRecallMessageData"):
                    i = d["deltaRecallMessageData"]
                    thread_id, thread_type = getThreadIdAndThreadType(i)
                    mid = i["messageID"]
                    ts = i["deletionTimestamp"]
                    author_id = str(i["senderID"])
                    self.onMessageUnsent(
                        mid=mid,
                        author_id=author_id,
                        thread_id=thread_id,
                        thread_type=thread_type,
                        ts=ts,
                        msg=m,
                    )

        # New message
        elif delta.get("class") == "NewMessage":
            mentions = []
            if delta.get("data") and delta["data"].get("prng"):
                try:
                    mentions = [
                        Mention(
                            str(mention.get("i")),
                            offset=mention.get("o"),
                            length=mention.get("l"),
                        )
                        for mention in parse_json(delta["data"]["prng"])
                    ]
                except Exception:
                    log.exception("An exception occured while reading attachments")

            sticker = None
            attachments = []
            unsent = False
            if delta.get("attachments"):
                try:
                    for a in delta["attachments"]:
                        mercury = a["mercury"]
                        if mercury.get("blob_attachment"):
                            image_metadata = a.get("imageMetadata", {})
                            attach_type = mercury["blob_attachment"]["__typename"]
                            attachment = graphql_to_attachment(
                                mercury["blob_attachment"]
                            )

                            if attach_type in [
                                "MessageFile",
                                "MessageVideo",
                                "MessageAudio",
                            ]:
                                # TODO: Add more data here for audio files
                                attachment.size = int(a["fileSize"])
                            attachments.append(attachment)

                        elif mercury.get("sticker_attachment"):
                            sticker = graphql_to_sticker(mercury["sticker_attachment"])

                        elif mercury.get("extensible_attachment"):
                            attachment = graphql_to_extensible_attachment(
                                mercury["extensible_attachment"]
                            )
                            if isinstance(attachment, UnsentMessage):
                                unsent = True
                            elif attachment:
                                attachments.append(attachment)

                except Exception:
                    log.exception(
                        "An exception occured while reading attachments: {}".format(
                            delta["attachments"]
                        )
                    )

            if metadata and metadata.get("tags"):
                emoji_size = get_emojisize_from_tags(metadata.get("tags"))

            message = Message(
                text=delta.get("body"),
                mentions=mentions,
                emoji_size=emoji_size,
                sticker=sticker,
                attachments=attachments,
            )
            message.uid = mid
            message.author = author_id
            message.timestamp = ts
            # message.reactions = {}
            message.unsent = unsent
            thread_id, thread_type = getThreadIdAndThreadType(metadata)
            self.onMessage(
                mid=mid,
                author_id=author_id,
                message=delta.get("body", ""),
                message_object=message,
                thread_id=thread_id,
                thread_type=thread_type,
                ts=ts,
                metadata=metadata,
                msg=m,
            )

        # Unknown message type
        else:
            self.onUnknownMesssageType(msg=m)

    def _parseMessage(self, content):
        """Get message and author name from content. May contain multiple messages in the content."""

        if "lb_info" in content:
            self.sticky = content["lb_info"]["sticky"]
            self.pool = content["lb_info"]["pool"]

        if "batches" in content:
            for batch in content["batches"]:
                self._parseMessage(batch)

        if "ms" not in content:
            return

        for m in content["ms"]:
            mtype = m.get("type")
            try:
                # Things that directly change chat
                if mtype == "delta":
                    self._parseDelta(m)
                # Inbox
                elif mtype == "inbox":
                    self.onInbox(
                        unseen=m["unseen"],
                        unread=m["unread"],
                        recent_unread=m["recent_unread"],
                        msg=m,
                    )

                # Typing
                elif mtype == "typ" or mtype == "ttyp":
                    author_id = str(m.get("from"))
                    thread_id = m.get("thread_fbid")
                    if thread_id:
                        thread_type = ThreadType.GROUP
                        thread_id = str(thread_id)
                    else:
                        thread_type = ThreadType.USER
                        if author_id == self.uid:
                            thread_id = m.get("to")
                        else:
                            thread_id = author_id
                    typing_status = TypingStatus(m.get("st"))
                    self.onTyping(
                        author_id=author_id,
                        status=typing_status,
                        thread_id=thread_id,
                        thread_type=thread_type,
                        msg=m,
                    )

                # Delivered

                # Seen
                # elif mtype == "m_read_receipt":
                #
                #     self.onSeen(m.get('realtime_viewer_fbid'), m.get('reader'), m.get('time'))

                elif mtype in ["jewel_requests_add"]:
                    from_id = m["from"]
                    self.onFriendRequest(from_id=from_id, msg=m)

                # Happens on every login
                elif mtype == "qprimer":
                    self.onQprimer(ts=m.get("made"), msg=m)

                # Is sent before any other message
                elif mtype == "deltaflow":
                    pass

                # Chat timestamp
                elif mtype == "chatproxy-presence":
                    buddylist = dict()
                    for _id in m.get("buddyList", {}):
                        payload = m["buddyList"][_id]

                        last_active = payload.get("lat")
                        active = payload.get("p") in [2, 3]
                        in_game = int(_id) in m.get("gamers", {})

                        buddylist[_id] = last_active

                        if self._buddylist.get(_id):
                            self._buddylist[_id].last_active = last_active
                            self._buddylist[_id].active = active
                            self._buddylist[_id].in_game = in_game
                        else:
                            self._buddylist[_id] = ActiveStatus(
                                active=active, last_active=last_active, in_game=in_game
                            )

                    self.onChatTimestamp(buddylist=buddylist, msg=m)

                # Buddylist overlay
                elif mtype == "buddylist_overlay":
                    statuses = dict()
                    for _id in m.get("overlay", {}):
                        payload = m["overlay"][_id]

                        last_active = payload.get("la")
                        active = payload.get("a") in [2, 3]
                        in_game = (
                            self._buddylist[_id].in_game
                            if self._buddylist.get(_id)
                            else False
                        )

                        status = ActiveStatus(
                            active=active, last_active=last_active, in_game=in_game
                        )

                        if self._buddylist.get(_id):
                            self._buddylist[_id].last_active = last_active
                            self._buddylist[_id].active = active
                            self._buddylist[_id].in_game = in_game
                        else:
                            self._buddylist[_id] = status

                        statuses[_id] = status

                    self.onBuddylistOverlay(statuses=statuses, msg=m)

                # Unknown message type
                else:
                    self.onUnknownMesssageType(msg=m)

            except Exception as e:
                self.onMessageError(exception=e, msg=m)

    def startListening(self):
        """
        Start listening from an external event loop

        :raises: FBchatException if request failed
        """
        self.listening = True

    def doOneListen(self, markAlive=None):
        """
        Does one cycle of the listening loop.
        This method is useful if you want to control fbchat from an external event loop

        .. warning::
            `markAlive` parameter is deprecated now, use :func:`fbchat.Client.setActiveStatus`
            or `markAlive` parameter in :func:`fbchat.Client.listen` instead.

        :return: Whether the loop should keep running
        :rtype: bool
        """
        if markAlive is not None:
            self._markAlive = markAlive
        try:
            if self._markAlive:
                self._ping()
            content = self._pullMessage()
            if content:
                self._parseMessage(content)
        except KeyboardInterrupt:
            return False
        except requests.Timeout:
            pass
        except requests.ConnectionError:
            # If the client has lost their internet connection, keep trying every 30 seconds
            time.sleep(30)
        except FBchatFacebookError as e:
            # Fix 502 and 503 pull errors
            if e.request_status_code in [502, 503]:
                self.req_url.change_pull_channel()
                self.startListening()
            else:
                raise e
        except Exception as e:
            return self.onListenError(exception=e)

        return True

    def stopListening(self):
        """Cleans up the variables from startListening"""
        self.listening = False
        self.sticky, self.pool = (None, None)

    def listen(self, markAlive=None):
        """
        Initializes and runs the listening loop continually

        :param markAlive: Whether this should ping the Facebook server each time the loop runs
        :type markAlive: bool
        """
        if markAlive is not None:
            self.setActiveStatus(markAlive)

        self.startListening()
        self.onListening()

        while self.listening and self.doOneListen():
            pass

        self.stopListening()

    def setActiveStatus(self, markAlive):
        """
        Changes client active status while listening

        :param markAlive: Whether to show if client is active
        :type markAlive: bool
        """
        self._markAlive = markAlive

    """
    END LISTEN METHODS
    """

    """
    EVENTS
    """

    def onLoggingIn(self, email=None):
        """
        Called when the client is logging in

        :param email: The email of the client
        """
        log.info("Logging in {}...".format(email))

    def on2FACode(self):
        """Called when a 2FA code is needed to progress"""
        return input("Please enter your 2FA code --> ")

    def onLoggedIn(self, email=None):
        """
        Called when the client is successfully logged in

        :param email: The email of the client
        """
        log.info("Login of {} successful.".format(email))

    def onListening(self):
        """Called when the client is listening"""
        log.info("Listening...")

    def onListenError(self, exception=None):
        """
        Called when an error was encountered while listening

        :param exception: The exception that was encountered
        :return: Whether the loop should keep running
        """
        log.exception("Got exception while listening")
        return True

    def onMessage(
            self,
            mid=None,
            author_id=None,
            message=None,
            message_object=None,
            thread_id=None,
            thread_type=ThreadType.USER,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody sends a message

        :param mid: The message ID
        :param author_id: The ID of the author
        :param message: (deprecated. Use `message_object.text` instead)
        :param message_object: The message (As a `Message` object)
        :param thread_id: Thread ID that the message was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the message was sent to. See :ref:`intro_threads`
        :param ts: The timestamp of the message
        :param metadata: Extra metadata about the message
        :param msg: A full set of the data recieved
        :type message_object: models.Message
        :type thread_type: models.ThreadType
        """
        log.info("{} from {} in {}".format(message_object, thread_id, thread_type.name))

    def onColorChange(
            self,
            mid=None,
            author_id=None,
            new_color=None,
            thread_id=None,
            thread_type=ThreadType.USER,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody changes a thread's color

        :param mid: The action ID
        :param author_id: The ID of the person who changed the color
        :param new_color: The new color
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type new_color: models.ThreadColor
        :type thread_type: models.ThreadType
        """
        log.info(
            "Color change from {} in {} ({}): {}".format(
                author_id, thread_id, thread_type.name, new_color
            )
        )

    def onEmojiChange(
            self,
            mid=None,
            author_id=None,
            new_emoji=None,
            thread_id=None,
            thread_type=ThreadType.USER,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody changes a thread's emoji

        :param mid: The action ID
        :param author_id: The ID of the person who changed the emoji
        :param new_emoji: The new emoji
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "Emoji change from {} in {} ({}): {}".format(
                author_id, thread_id, thread_type.name, new_emoji
            )
        )

    def onTitleChange(
            self,
            mid=None,
            author_id=None,
            new_title=None,
            thread_id=None,
            thread_type=ThreadType.USER,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody changes the title of a thread

        :param mid: The action ID
        :param author_id: The ID of the person who changed the title
        :param new_title: The new title
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "Title change from {} in {} ({}): {}".format(
                author_id, thread_id, thread_type.name, new_title
            )
        )

    def onImageChange(
            self,
            mid=None,
            author_id=None,
            new_image=None,
            thread_id=None,
            thread_type=ThreadType.GROUP,
            ts=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody changes the image of a thread

        :param mid: The action ID
        :param author_id: The ID of the person who changed the image
        :param new_image: The ID of the new image
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info("{} changed thread image in {}".format(author_id, thread_id))

    def onNicknameChange(
            self,
            mid=None,
            author_id=None,
            changed_for=None,
            new_nickname=None,
            thread_id=None,
            thread_type=ThreadType.USER,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody changes the nickname of a person

        :param mid: The action ID
        :param author_id: The ID of the person who changed the nickname
        :param changed_for: The ID of the person whom got their nickname changed
        :param new_nickname: The new nickname
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "Nickname change from {} in {} ({}) for {}: {}".format(
                author_id, thread_id, thread_type.name, changed_for, new_nickname
            )
        )

    def onAdminAdded(
            self,
            mid=None,
            added_id=None,
            author_id=None,
            thread_id=None,
            thread_type=ThreadType.GROUP,
            ts=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody adds an admin to a group thread

        :param mid: The action ID
        :param added_id: The ID of the admin who got added
        :param author_id: The ID of the person who added the admins
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        """
        log.info("{} added admin: {} in {}".format(author_id, added_id, thread_id))

    def onAdminRemoved(
            self,
            mid=None,
            removed_id=None,
            author_id=None,
            thread_id=None,
            thread_type=ThreadType.GROUP,
            ts=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody removes an admin from a group thread

        :param mid: The action ID
        :param removed_id: The ID of the admin who got removed
        :param author_id: The ID of the person who removed the admins
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        """
        log.info("{} removed admin: {} in {}".format(author_id, removed_id, thread_id))

    def onApprovalModeChange(
            self,
            mid=None,
            approval_mode=None,
            author_id=None,
            thread_id=None,
            thread_type=ThreadType.GROUP,
            ts=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody changes approval mode in a group thread

        :param mid: The action ID
        :param approval_mode: True if approval mode is activated
        :param author_id: The ID of the person who changed approval mode
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        """
        if approval_mode:
            log.info("{} activated approval mode in {}".format(author_id, thread_id))
        else:
            log.info("{} disabled approval mode in {}".format(author_id, thread_id))

    def onMessageSeen(
            self,
            seen_by=None,
            thread_id=None,
            thread_type=ThreadType.USER,
            seen_ts=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody marks a message as seen

        :param seen_by: The ID of the person who marked the message as seen
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param seen_ts: A timestamp of when the person saw the message
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "Messages seen by {} in {} ({}) at {}s".format(
                seen_by, thread_id, thread_type.name, seen_ts / 1000
            )
        )

    def onMessageDelivered(
            self,
            msg_ids=None,
            delivered_for=None,
            thread_id=None,
            thread_type=ThreadType.USER,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody marks messages as delivered

        :param msg_ids: The messages that are marked as delivered
        :param delivered_for: The person that marked the messages as delivered
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "Messages {} delivered to {} in {} ({}) at {}s".format(
                msg_ids, delivered_for, thread_id, thread_type.name, ts / 1000
            )
        )

    def onMarkedSeen(
            self, threads=None, seen_ts=None, ts=None, metadata=None, msg=None
    ):
        """
        Called when the client is listening, and the client has successfully marked threads as seen

        :param threads: The threads that were marked
        :param author_id: The ID of the person who changed the emoji
        :param seen_ts: A timestamp of when the threads were seen
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "Marked messages as seen in threads {} at {}s".format(
                [(x[0], x[1].name) for x in threads], seen_ts / 1000
            )
        )

    def onMessageUnsent(
            self,
            mid=None,
            author_id=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            msg=None,
    ):
        """
        Called when the client is listening, and someone unsends (deletes for everyone) a message

        :param mid: ID of the unsent message
        :param author_id: The ID of the person who unsent the message
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} unsent the message {} in {} ({}) at {}s".format(
                author_id, repr(mid), thread_id, thread_type.name, ts / 1000
            )
        )

    def onPeopleAdded(
            self,
            mid=None,
            added_ids=None,
            author_id=None,
            thread_id=None,
            ts=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody adds people to a group thread

        :param mid: The action ID
        :param added_ids: The IDs of the people who got added
        :param author_id: The ID of the person who added the people
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        """
        log.info(
            "{} added: {} in {}".format(author_id, ", ".join(added_ids), thread_id)
        )

    def onPersonRemoved(
            self,
            mid=None,
            removed_id=None,
            author_id=None,
            thread_id=None,
            ts=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody removes a person from a group thread

        :param mid: The action ID
        :param removed_id: The ID of the person who got removed
        :param author_id: The ID of the person who removed the person
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        """
        log.info("{} removed: {} in {}".format(author_id, removed_id, thread_id))

    def onFriendRequest(self, from_id=None, msg=None):
        """
        Called when the client is listening, and somebody sends a friend request

        :param from_id: The ID of the person that sent the request
        :param msg: A full set of the data recieved
        """
        log.info("Friend request from {}".format(from_id))

    def onInbox(self, unseen=None, unread=None, recent_unread=None, msg=None):
        """
        .. todo::
            Documenting this

        :param unseen: --
        :param unread: --
        :param recent_unread: --
        :param msg: A full set of the data recieved
        """
        log.info("Inbox event: {}, {}, {}".format(unseen, unread, recent_unread))

    def onTyping(
            self, author_id=None, status=None, thread_id=None, thread_type=None, msg=None
    ):
        """
        Called when the client is listening, and somebody starts or stops typing into a chat

        :param author_id: The ID of the person who sent the action
        :param status: The typing status
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param msg: A full set of the data recieved
        :type typing_status: models.TypingStatus
        :type thread_type: models.ThreadType
        """
        pass

    def onGamePlayed(
            self,
            mid=None,
            author_id=None,
            game_id=None,
            game_name=None,
            score=None,
            leaderboard=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody plays a game

        :param mid: The action ID
        :param author_id: The ID of the person who played the game
        :param game_id: The ID of the game
        :param game_name: Name of the game
        :param score: Score obtained in the game
        :param leaderboard: Actual leaderboard of the game in the thread
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            '{} played "{}" in {} ({})'.format(
                author_id, game_name, thread_id, thread_type.name
            )
        )

    def onReactionAdded(
            self,
            mid=None,
            reaction=None,
            author_id=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody reacts to a message

        :param mid: Message ID, that user reacted to
        :param reaction: Reaction
        :param add_reaction: Whether user added or removed reaction
        :param author_id: The ID of the person who reacted to the message
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        :type reaction: models.MessageReaction
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} reacted to message {} with {} in {} ({})".format(
                author_id, mid, reaction.name, thread_id, thread_type.name
            )
        )

    def onReactionRemoved(
            self,
            mid=None,
            author_id=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody removes reaction from a message

        :param mid: Message ID, that user reacted to
        :param author_id: The ID of the person who removed reaction
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} removed reaction from {} message in {} ({})".format(
                author_id, mid, thread_id, thread_type
            )
        )

    def onBlock(
            self, author_id=None, thread_id=None, thread_type=None, ts=None, msg=None
    ):
        """
        Called when the client is listening, and somebody blocks client

        :param author_id: The ID of the person who blocked
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} blocked {} ({}) thread".format(author_id, thread_id, thread_type.name)
        )

    def onUnblock(
            self, author_id=None, thread_id=None, thread_type=None, ts=None, msg=None
    ):
        """
        Called when the client is listening, and somebody blocks client

        :param author_id: The ID of the person who unblocked
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} unblocked {} ({}) thread".format(author_id, thread_id, thread_type.name)
        )

    def onLiveLocation(
            self,
            mid=None,
            location=None,
            author_id=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            msg=None,
    ):
        """
        Called when the client is listening and somebody sends live location info

        :param mid: The action ID
        :param location: Sent location info
        :param author_id: The ID of the person who sent location info
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        :type location: models.LiveLocationAttachment
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} sent live location info in {} ({}) with latitude {} and longitude {}".format(
                author_id, thread_id, thread_type, location.latitude, location.longitude
            )
        )

    def onCallStarted(
            self,
            mid=None,
            caller_id=None,
            is_video_call=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        .. todo::
            Make this work with private calls

        Called when the client is listening, and somebody starts a call in a group

        :param mid: The action ID
        :param caller_id: The ID of the person who started the call
        :param is_video_call: True if it's video call
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} started call in {} ({})".format(caller_id, thread_id, thread_type.name)
        )

    def onCallEnded(
            self,
            mid=None,
            caller_id=None,
            is_video_call=None,
            call_duration=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        .. todo::
            Make this work with private calls

        Called when the client is listening, and somebody ends a call in a group

        :param mid: The action ID
        :param caller_id: The ID of the person who ended the call
        :param is_video_call: True if it was video call
        :param call_duration: Call duration in seconds
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} ended call in {} ({})".format(caller_id, thread_id, thread_type.name)
        )

    def onUserJoinedCall(
            self,
            mid=None,
            joined_id=None,
            is_video_call=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody joins a group call

        :param mid: The action ID
        :param joined_id: The ID of the person who joined the call
        :param is_video_call: True if it's video call
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} joined call in {} ({})".format(joined_id, thread_id, thread_type.name)
        )

    def onPollCreated(
            self,
            mid=None,
            poll=None,
            author_id=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody creates a group poll

        :param mid: The action ID
        :param poll: Created poll
        :param author_id: The ID of the person who created the poll
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type poll: models.Poll
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} created poll {} in {} ({})".format(
                author_id, poll, thread_id, thread_type.name
            )
        )

    def onPollVoted(
            self,
            mid=None,
            poll=None,
            added_options=None,
            removed_options=None,
            author_id=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody votes in a group poll

        :param mid: The action ID
        :param poll: Poll, that user voted in
        :param author_id: The ID of the person who voted in the poll
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type poll: models.Poll
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} voted in poll {} in {} ({})".format(
                author_id, poll, thread_id, thread_type.name
            )
        )

    def onPlanCreated(
            self,
            mid=None,
            plan=None,
            author_id=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody creates a plan

        :param mid: The action ID
        :param plan: Created plan
        :param author_id: The ID of the person who created the plan
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type plan: models.Plan
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} created plan {} in {} ({})".format(
                author_id, plan, thread_id, thread_type.name
            )
        )

    def onPlanEnded(
            self,
            mid=None,
            plan=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and a plan ends

        :param mid: The action ID
        :param plan: Ended plan
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type plan: models.Plan
        :type thread_type: models.ThreadType
        """
        log.info(
            "Plan {} has ended in {} ({})".format(plan, thread_id, thread_type.name)
        )

    def onPlanEdited(
            self,
            mid=None,
            plan=None,
            author_id=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody edits a plan

        :param mid: The action ID
        :param plan: Edited plan
        :param author_id: The ID of the person who edited the plan
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type plan: models.Plan
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} edited plan {} in {} ({})".format(
                author_id, plan, thread_id, thread_type.name
            )
        )

    def onPlanDeleted(
            self,
            mid=None,
            plan=None,
            author_id=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody deletes a plan

        :param mid: The action ID
        :param plan: Deleted plan
        :param author_id: The ID of the person who deleted the plan
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type plan: models.Plan
        :type thread_type: models.ThreadType
        """
        log.info(
            "{} deleted plan {} in {} ({})".format(
                author_id, plan, thread_id, thread_type.name
            )
        )

    def onPlanParticipation(
            self,
            mid=None,
            plan=None,
            take_part=None,
            author_id=None,
            thread_id=None,
            thread_type=None,
            ts=None,
            metadata=None,
            msg=None,
    ):
        """
        Called when the client is listening, and somebody takes part in a plan or not

        :param mid: The action ID
        :param plan: Plan
        :param take_part: Whether the person takes part in the plan or not
        :param author_id: The ID of the person who will participate in the plan or not
        :param thread_id: Thread ID that the action was sent to. See :ref:`intro_threads`
        :param thread_type: Type of thread that the action was sent to. See :ref:`intro_threads`
        :param ts: A timestamp of the action
        :param metadata: Extra metadata about the action
        :param msg: A full set of the data recieved
        :type plan: models.Plan
        :type take_part: bool
        :type thread_type: models.ThreadType
        """
        if take_part:
            log.info(
                "{} will take part in {} in {} ({})".format(
                    author_id, plan, thread_id, thread_type.name
                )
            )
        else:
            log.info(
                "{} won't take part in {} in {} ({})".format(
                    author_id, plan, thread_id, thread_type.name
                )
            )

    def onQprimer(self, ts=None, msg=None):
        """
        Called when the client just started listening

        :param ts: A timestamp of the action
        :param msg: A full set of the data recieved
        """
        pass

    def onChatTimestamp(self, buddylist=None, msg=None):
        """
        Called when the client receives chat online presence update

        :param buddylist: A list of dicts with friend id and last seen timestamp
        :param msg: A full set of the data recieved
        """
        log.debug("Chat Timestamps received: {}".format(buddylist))

    def onBuddylistOverlay(self, statuses=None, msg=None):
        """
        Called when the client is listening and client receives information about friend active status

        :param statuses: Dictionary with user IDs as keys and :class:`models.ActiveStatus` as values
        :param msg: A full set of the data recieved
        :type statuses: dict
        """
        log.debug("Buddylist overlay received: {}".format(statuses))

    def onUnknownMesssageType(self, msg=None):
        """
        Called when the client is listening, and some unknown data was recieved

        :param msg: A full set of the data recieved
        """
        log.debug("Unknown message received: {}".format(msg))

    def onMessageError(self, exception=None, msg=None):
        """
        Called when an error was encountered while parsing recieved data

        :param exception: The exception that was encountered
        :param msg: A full set of the data recieved
        """
        log.exception("Exception in parsing of {}".format(msg))

    """
    END EVENTS
    """
