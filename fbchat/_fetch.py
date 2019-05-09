from .models import *
from .graphql import *
import time

class Fetcher(object):

    def __init__(self, initial):
        self.placehold = initial



    """
    FETCH METHODS
    """

    def FET__forcedFetch(self, Client, thread_id, mid):
        j = Client.graphql_request(
            GraphQL(
                doc_id="1768656253222505",
                params={
                    "thread_and_message_id": {"thread_id": thread_id, "message_id": mid}
                },
            )
        )
        return j

    def FET_fetchThreads(self, Client, thread_location, before=None, after=None, limit=None):
        """
        Get all threads in thread_location.
        Threads will be sorted from newest to oldest.

        :param thread_location: models.ThreadLocation: INBOX, PENDING, ARCHIVED or OTHER
        :param before: Fetch only thread before this epoch (in ms) (default all threads)
        :param after: Fetch only thread after this epoch (in ms) (default all threads)
        :param limit: The max. amount of threads to fetch (default all threads)
        :return: :class:`models.Thread` objects
        :rtype: list
        :raises: FBchatException if request failed
        """
        threads = []

        last_thread_timestamp = None
        while True:
            # break if limit is exceeded
            if limit and len(threads) >= limit:
                break

            # fetchThreadList returns at max 20 threads before last_thread_timestamp (included)
            candidates = Client.fetchThreadList(
                before=last_thread_timestamp, thread_location=thread_location
            )

            if len(candidates) > 1:
                threads += candidates[1:]
            else:  # End of threads
                break

            last_thread_timestamp = threads[-1].last_message_timestamp

            # FB returns a sorted list of threads
            if (before is not None and int(last_thread_timestamp) > before) or (
                after is not None and int(last_thread_timestamp) < after
            ):
                break

        # Return only threads between before and after (if set)
        if before is not None or after is not None:
            for t in threads:
                last_message_timestamp = int(t.last_message_timestamp)
                if (before is not None and last_message_timestamp > before) or (
                    after is not None and last_message_timestamp < after
                ):
                    threads.remove(t)

        if limit and len(threads) > limit:
            return threads[:limit]

        return threads

    def FET_fetchAllUsersFromThreads(self, Client, threads):
        """
        Get all users involved in threads.

        :param threads: models.Thread: List of threads to check for users
        :return: :class:`models.User` objects
        :rtype: list
        :raises: FBchatException if request failed
        """
        users = []
        users_to_fetch = []  # It's more efficient to fetch all users in one request
        for thread in threads:
            if thread.type == ThreadType.USER:
                if thread.uid not in [user.uid for user in users]:
                    users.append(thread)
            elif thread.type == ThreadType.GROUP:
                for user_id in thread.participants:
                    if (
                        user_id not in [user.uid for user in users]
                        and user_id not in users_to_fetch
                    ):
                        users_to_fetch.append(user_id)
            else:
                pass
        for user_id, user in Client.fetchUserInfo(*users_to_fetch).items():
            users.append(user)
        return users

    def FET_fetchAllUsers(self, Client):
        """
        Gets all users the client is currently chatting with

        :return: :class:`models.User` objects
        :rtype: list
        :raises: FBchatException if request failed
        """

        data = {"viewer": Client.uid}
        j = Client._post(
            Client.req_url.ALL_USERS, query=data, fix_request=True, as_json=True
        )
        if j.get("payload") is None:
            raise FBchatException("Missing payload while fetching users: {}".format(j))

        users = []

        for key in j["payload"]:
            k = j["payload"][key]
            if k["type"] in ["user", "friend"]:
                if k["id"] in ["0", 0]:
                    # Skip invalid users
                    pass
                users.append(
                    User(
                        k["id"],
                        first_name=k.get("firstName"),
                        url=k.get("uri"),
                        photo=k.get("thumbSrc"),
                        name=k.get("name"),
                        is_friend=k.get("is_friend"),
                        gender=GENDERS.get(k.get("gender")),
                    )
                )

        return users

    def FET_searchForUsers(self, Client, name, limit=10):
        """
        Find and get user by his/her name

        :param name: Name of the user
        :param limit: The max. amount of users to fetch
        :return: :class:`models.User` objects, ordered by relevance
        :rtype: list
        :raises: FBchatException if request failed
        """

        j = Client.graphql_request(
            GraphQL(query=GraphQL.SEARCH_USER, params={"search": name, "limit": limit})
        )

        return [graphql_to_user(node) for node in j[name]["users"]["nodes"]]

    def FET_searchForPages(self, Client, name, limit=10):
        """
        Find and get page by its name

        :param name: Name of the page
        :return: :class:`models.Page` objects, ordered by relevance
        :rtype: list
        :raises: FBchatException if request failed
        """

        j = Client.graphql_request(
            GraphQL(query=GraphQL.SEARCH_PAGE, params={"search": name, "limit": limit})
        )

        return [graphql_to_page(node) for node in j[name]["pages"]["nodes"]]

    def FET_searchForGroups(self, Client, name, limit=10):
        """
        Find and get group thread by its name

        :param name: Name of the group thread
        :param limit: The max. amount of groups to fetch
        :return: :class:`models.Group` objects, ordered by relevance
        :rtype: list
        :raises: FBchatException if request failed
        """

        j = Client.graphql_request(
            GraphQL(query=GraphQL.SEARCH_GROUP, params={"search": name, "limit": limit})
        )

        return [graphql_to_group(node) for node in j["viewer"]["groups"]["nodes"]]

    def FET_searchForThreads(self, Client, name, limit=10):
        """
        Find and get a thread by its name

        :param name: Name of the thread
        :param limit: The max. amount of groups to fetch
        :return: :class:`models.User`, :class:`models.Group` and :class:`models.Page` objects, ordered by relevance
        :rtype: list
        :raises: FBchatException if request failed
        """

        j = Client.graphql_request(
            GraphQL(
                query=GraphQL.SEARCH_THREAD, params={"search": name, "limit": limit}
            )
        )

        rtn = []
        for node in j[name]["threads"]["nodes"]:
            if node["__typename"] == "User":
                rtn.append(graphql_to_user(node))
            elif node["__typename"] == "MessageThread":
                # MessageThread => Group thread
                rtn.append(graphql_to_group(node))
            elif node["__typename"] == "Page":
                rtn.append(graphql_to_page(node))
            elif node["__typename"] == "Group":
                # We don't handle Facebook "Groups"
                pass
            else:
                log.warning(
                    "Unknown __typename: {} in {}".format(
                        repr(node["__typename"]), node
                    )
                )

        return rtn

    def FET_searchForMessageIDs(self, Client, query, offset=0, limit=5, thread_id=None):
        """
        Find and get message IDs by query

        :param query: Text to search for
        :param offset: Number of messages to skip
        :param limit: Max. number of messages to retrieve
        :param thread_id: User/Group ID to search in. See :ref:`intro_threads`
        :type offset: int
        :type limit: int
        :return: Found Message IDs
        :rtype: generator
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = Client._getThread(thread_id, None)

        data = {
            "query": query,
            "snippetOffset": offset,
            "snippetLimit": limit,
            "identifier": "thread_fbid",
            "thread_fbid": thread_id,
        }
        j = Client._post(
            Client.req_url.SEARCH_MESSAGES, data, fix_request=True, as_json=True
        )

        result = j["payload"]["search_snippets"][query]
        snippets = result[thread_id]["snippets"] if result.get(thread_id) else []
        for snippet in snippets:
            yield snippet["message_id"]

    def FET_searchForMessages(self, Client, query, offset=0, limit=5, thread_id=None):
        """
        Find and get :class:`models.Message` objects by query

        .. warning::
            This method sends request for every found message ID.

        :param query: Text to search for
        :param offset: Number of messages to skip
        :param limit: Max. number of messages to retrieve
        :param thread_id: User/Group ID to search in. See :ref:`intro_threads`
        :type offset: int
        :type limit: int
        :return: Found :class:`models.Message` objects
        :rtype: generator
        :raises: FBchatException if request failed
        """
        message_ids = Client.searchForMessageIDs(
            query, offset=offset, limit=limit, thread_id=thread_id
        )
        for mid in message_ids:
            yield Client.fetchMessageInfo(mid, thread_id)

    def FET_search(self, Client, query, fetch_messages=False, thread_limit=5, message_limit=5):
        """
        Searches for messages in all threads

        :param query: Text to search for
        :param fetch_messages: Whether to fetch :class:`models.Message` objects or IDs only
        :param thread_limit: Max. number of threads to retrieve
        :param message_limit: Max. number of messages to retrieve
        :type thread_limit: int
        :type message_limit: int
        :return: Dictionary with thread IDs as keys and generators to get messages as values
        :rtype: generator
        :raises: FBchatException if request failed
        """
        data = {"query": query, "snippetLimit": thread_limit}
        j = Client._post(
            Client.req_url.SEARCH_MESSAGES, data, fix_request=True, as_json=True
        )

        result = j["payload"]["search_snippets"][query]

        if fetch_messages:
            return {
                thread_id: Client.searchForMessages(
                    query, limit=message_limit, thread_id=thread_id
                )
                for thread_id in result
            }
        else:
            return {
                thread_id: Client.searchForMessageIDs(
                    query, limit=message_limit, thread_id=thread_id
                )
                for thread_id in result
            }

    def FET__fetchInfo(self, Client, *ids):
        data = {"ids[{}]".format(i): _id for i, _id in enumerate(ids)}
        j = Client._post(Client.req_url.INFO, data, fix_request=True, as_json=True)

        if j.get("payload") is None or j["payload"].get("profiles") is None:
            raise FBchatException("No users/pages returned: {}".format(j))

        entries = {}
        for _id in j["payload"]["profiles"]:
            k = j["payload"]["profiles"][_id]
            if k["type"] in ["user", "friend"]:
                entries[_id] = {
                    "id": _id,
                    "type": ThreadType.USER,
                    "url": k.get("uri"),
                    "first_name": k.get("firstName"),
                    "is_viewer_friend": k.get("is_friend"),
                    "gender": k.get("gender"),
                    "profile_picture": {"uri": k.get("thumbSrc")},
                    "name": k.get("name"),
                }
            elif k["type"] == "page":
                entries[_id] = {
                    "id": _id,
                    "type": ThreadType.PAGE,
                    "url": k.get("uri"),
                    "profile_picture": {"uri": k.get("thumbSrc")},
                    "name": k.get("name"),
                }
            else:
                raise FBchatException(
                    "{} had an unknown thread type: {}".format(_id, k)
                )

        log.debug(entries)
        return entries

    def FET_fetchUserInfo(self, Client, *user_ids):
        """
        Get users' info from IDs, unordered

        .. warning::
            Sends two requests, to fetch all available info!

        :param user_ids: One or more user ID(s) to query
        :return: :class:`models.User` objects, labeled by their ID
        :rtype: dict
        :raises: FBchatException if request failed
        """

        threads = Client.fetchThreadInfo(*user_ids)
        users = {}
        for k in threads:
            if threads[k].type == ThreadType.USER:
                users[k] = threads[k]
            else:
                raise FBchatUserError("Thread {} was not a user".format(threads[k]))

        return users

    def FET_fetchPageInfo(self, Client, *page_ids):
        """
        Get pages' info from IDs, unordered

        .. warning::
            Sends two requests, to fetch all available info!

        :param page_ids: One or more page ID(s) to query
        :return: :class:`models.Page` objects, labeled by their ID
        :rtype: dict
        :raises: FBchatException if request failed
        """

        threads = Client.fetchThreadInfo(*page_ids)
        pages = {}
        for k in threads:
            if threads[k].type == ThreadType.PAGE:
                pages[k] = threads[k]
            else:
                raise FBchatUserError("Thread {} was not a page".format(threads[k]))

        return pages

    def FET_fetchGroupInfo(self, Client, *group_ids):
        """
        Get groups' info from IDs, unordered

        :param group_ids: One or more group ID(s) to query
        :return: :class:`models.Group` objects, labeled by their ID
        :rtype: dict
        :raises: FBchatException if request failed
        """

        threads = Client.fetchThreadInfo(*group_ids)
        groups = {}
        for k in threads:
            if threads[k].type == ThreadType.GROUP:
                groups[k] = threads[k]
            else:
                raise FBchatUserError("Thread {} was not a group".format(threads[k]))

        return groups

    def FET_fetchThreadInfo(self, Client, *thread_ids):
        """
        Get threads' info from IDs, unordered

        .. warning::
            Sends two requests if users or pages are present, to fetch all available info!

        :param thread_ids: One or more thread ID(s) to query
        :return: :class:`models.Thread` objects, labeled by their ID
        :rtype: dict
        :raises: FBchatException if request failed
        """

        queries = []
        for thread_id in thread_ids:
            queries.append(
                GraphQL(
                    doc_id="2147762685294928",
                    params={
                        "id": thread_id,
                        "message_limit": 0,
                        "load_messages": False,
                        "load_read_receipts": False,
                        "before": None,
                    },
                )
            )

        j = Client.graphql_requests(*queries)

        for i, entry in enumerate(j):
            if entry.get("message_thread") is None:
                # If you don't have an existing thread with this person, attempt to retrieve user data anyways
                j[i]["message_thread"] = {
                    "thread_key": {"other_user_id": thread_ids[i]},
                    "thread_type": "ONE_TO_ONE",
                }

        pages_and_user_ids = [
            k["message_thread"]["thread_key"]["other_user_id"]
            for k in j
            if k["message_thread"].get("thread_type") == "ONE_TO_ONE"
        ]
        pages_and_users = {}
        if len(pages_and_user_ids) != 0:
            pages_and_users = Client._fetchInfo(*pages_and_user_ids)

        rtn = {}
        for i, entry in enumerate(j):
            entry = entry["message_thread"]
            if entry.get("thread_type") == "GROUP":
                _id = entry["thread_key"]["thread_fbid"]
                rtn[_id] = graphql_to_group(entry)
            elif entry.get("thread_type") == "ONE_TO_ONE":
                _id = entry["thread_key"]["other_user_id"]
                if pages_and_users.get(_id) is None:
                    raise FBchatException("Could not fetch thread {}".format(_id))
                entry.update(pages_and_users[_id])
                if entry["type"] == ThreadType.USER:
                    rtn[_id] = graphql_to_user(entry)
                else:
                    rtn[_id] = graphql_to_page(entry)
            else:
                raise FBchatException(
                    "{} had an unknown thread type: {}".format(thread_ids[i], entry)
                )

        return rtn

    def FET_fetchThreadMessages(self, Client, thread_id=None, limit=20, before=None):
        """
        Get the last messages in a thread

        :param thread_id: User/Group ID to get messages from. See :ref:`intro_threads`
        :param limit: Max. number of messages to retrieve
        :param before: A timestamp, indicating from which point to retrieve messages
        :type limit: int
        :type before: int
        :return: :class:`models.Message` objects
        :rtype: list
        :raises: FBchatException if request failed
        """

        thread_id, thread_type = Client._getThread(thread_id, None)

        j = Client.graphql_request(
            GraphQL(
                doc_id="1386147188135407",
                params={
                    "id": thread_id,
                    "message_limit": limit,
                    "load_messages": True,
                    "load_read_receipts": True,
                    "before": before,
                },
            )
        )

        if j.get("message_thread") is None:
            raise FBchatException("Could not fetch thread {}: {}".format(thread_id, j))

        messages = list(
            reversed(
                [
                    graphql_to_message(message)
                    for message in j["message_thread"]["messages"]["nodes"]
                ]
            )
        )
        read_receipts = j["message_thread"]["read_receipts"]["nodes"]

        for message in messages:
            for receipt in read_receipts:
                if int(receipt["watermark"]) >= int(message.timestamp):
                    message.read_by.append(receipt["actor"]["id"])

        return messages

    def FET_fetchUnreadFromThreadMessages(self, Client, thread_id=None):


        unreadMessages = Client.fetchThreadMessages(thread_id)

        #A checker for the type before printing the heading
        threadType = Client.fetchThreadInfo(thread_id)[thread_id].type.name
        threadName = Client.fetchThreadInfo(thread_id)[thread_id].name

        if threadName is None:
            threadName = " "

        emptyUnreadMessages = 0

        if(threadType == 'GROUP'):
            print("________________________  GROUP CONVERSATION: " + threadName +"__________________________________________")

        elif(threadType == 'USER'):
            print("________________________  USER CONVERSATION WITH: " + threadName +"__________________________________________")

        for unreadMessage in unreadMessages:

            if unreadMessage.is_read == False:

                emptyUnreadMessages = emptyUnreadMessages + 1

                theMessageUser = Client.fetchUserInfo(unreadMessage.author)
                theMessageUser[unreadMessage.author].name

                theName = theMessageUser[unreadMessage.author].name

                theTime = time.ctime(int(unreadMessage.timestamp) / 1000.0)

                theTextMessage = unreadMessage.text

                print(" ")
                print("-----------------------------------------------------")
                print("From: ",end="")
                print(theName)
                print("Time: ", end="")
                print(theTime)
                print("Message:")
                print("          ", end="")
                print(theTextMessage)
                print("-----------------------------------------------------")
                print(" ")

        if emptyUnreadMessages == 0:
            print(" ")
            print("-----------------------------------------------------")
            print("       NO UNREAD MESSAGES           ")
            print("-----------------------------------------------------")
            print(" ")

        if (threadType == 'GROUP'):
            print("________________________  END OF GROUP CONVERSATION: " + threadName + "__________________________________________")

        elif (threadType == 'USER'):
            print("________________________  END OF USER CONVERSATION WITH: " + threadName + "__________________________________________")


    def FET_fetchThreadList(self, Client, offset=None, limit=20, thread_location=ThreadLocation.INBOX, before=None):
        """Get thread list of your facebook account

        :param offset: Deprecated. Do not use!
        :param limit: Max. number of threads to retrieve. Capped at 20
        :param thread_location: models.ThreadLocation: INBOX, PENDING, ARCHIVED or OTHER
        :param before: A timestamp (in milliseconds), indicating from which point to retrieve threads
        :type limit: int
        :type before: int
        :return: :class:`models.Thread` objects
        :rtype: list
        :raises: FBchatException if request failed
        """

        if offset is not None:
            log.warning(
                "Using `offset` in `fetchThreadList` is no longer supported, since Facebook migrated to the use of GraphQL in this request. Use `before` instead"
            )

        if limit > 20 or limit < 1:
            raise FBchatUserError("`limit` should be between 1 and 20")

        if thread_location in ThreadLocation:
            loc_str = thread_location.value
        else:
            raise FBchatUserError('"thread_location" must be a value of ThreadLocation')

        j = Client.graphql_request(
            GraphQL(
                doc_id="1349387578499440",
                params={
                    "limit": limit,
                    "tags": [loc_str],
                    "before": before,
                    "includeDeliveryReceipts": True,
                    "includeSeqID": False,
                },
            )
        )

        return [
            graphql_to_thread(node) for node in j["viewer"]["message_threads"]["nodes"]
        ]

    def FET_fetchUnread(self, Client):
        """
        Get the unread thread list

        :return: List of unread thread ids
        :rtype: list
        :raises: FBchatException if request failed
        """
        form = {
            "folders[0]": "inbox",
            "client": "mercury",
            "last_action_timestamp": now() - 60 * 1000
            # 'last_action_timestamp': 0
        }

        j = Client._post(
            Client.req_url.UNREAD_THREADS, form, fix_request=True, as_json=True
        )

        payload = j["payload"]["unread_thread_fbids"][0]

        return payload["thread_fbids"] + payload["other_user_fbids"]

    def FET_fetchUnseen(self, Client):
        """
        Get the unseen (new) thread list

        :return: List of unseen thread ids
        :rtype: list
        :raises: FBchatException if request failed
        """
        j = Client._post(
            Client.req_url.UNSEEN_THREADS, None, fix_request=True, as_json=True
        )

        payload = j["payload"]["unseen_thread_fbids"][0]

        return payload["thread_fbids"] + payload["other_user_fbids"]


    def FET_fetchImageUrl(self, Client, image_id):
        """Fetches the url to the original image from an image attachment ID
        :param image_id: The image you want to fethc
        :type image_id: str
        :return: An url where you can download the original image
        :rtype: str
        :raises: FBchatException if request failed
        """
        image_id = str(image_id)
        j = check_request(
            Client._get(ReqUrl.ATTACHMENT_PHOTO, query={"photo_id": str(image_id)})
        )

        url = get_jsmods_require(j, 3)
        if url is None:
            raise FBchatException("Could not fetch image url from: {}".format(j))
        if ".jpg" in url or ".jpeg" in url or ".png" in url or ".tiff" in url or ".gif" in url:
            return url
        else:
            return "This attachment isn't an image or doesn't have a .jpg, .jpeg, .png, .tiff, or .gif extention"

    def FET_fetchVideoUrl(self, Client, video_id):
        """Fetches the url to the original video from an video attachment ID
        :param video_id: The video you want to fethc
        :type video_id: str
        :return: An url where you can download the original video
        :rtype: str
        :raises: FBchatException if request failed
        """
        video_id = str(video_id)
        j = check_request(
            Client._get(ReqUrl.ATTACHMENT_PHOTO, query={"photo_id": str(video_id)})
        )

        url = get_jsmods_require(j, 3)
        if url is None:
            raise FBchatException("Could not fetch video url from: {}".format(j))
        
        if ".webm" in url or ".mkv" in url or ".flv" in url or ".avi" in url or ".mov" in url or ".wmv" in url or ".mp4" in url or ".m4p" in url or ".m4v" in url:
            return url
        else:
            return "This attachment isn't an image or doesn't have a .webm, .mkv, .flv, .avi, .mov, .wmv, .mp4, .m4p or .m4v extention"

    def FET_fetchJSON(self, Client, attach_id):
        """Fetches the json file that contains the original image from an image attachment ID
        :param attach_id: The image you want to fethc
        :type attach_id: str
        :return: An url where you can download the original image
        :rtype: str
        :raises: FBchatException if request failed
        """
        attach_id = str(attach_id)
        j = check_request(
            Client._get(ReqUrl.ATTACHMENT_PHOTO, query={"photo_id": str(attach_id)})
        )

        json = "The formatted json file: {}".format(j)
        return json


    def FET_fetchMessageInfo(self, Client, mid, thread_id=None):
        """
        Fetches :class:`models.Message` object from the message id

        :param mid: Message ID to fetch from
        :param thread_id: User/Group ID to get message info from. See :ref:`intro_threads`
        :return: :class:`models.Message` object
        :rtype: models.Message
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = Client._getThread(thread_id, None)
        message_info = Client._forcedFetch(thread_id, mid).get("message")
        message = graphql_to_message(message_info)
        return message

    def FET_fetchPollOptions(self, Client, poll_id):
        """
        Fetches list of :class:`models.PollOption` objects from the poll id

        :param poll_id: Poll ID to fetch from
        :rtype: list
        :raises: FBchatException if request failed
        """
        data = {"question_id": poll_id}

        j = Client._post(
            Client.req_url.GET_POLL_OPTIONS, data, fix_request=True, as_json=True
        )

        return [graphql_to_poll_option(m) for m in j["payload"]]

    def FET_fetchPlanInfo(self, Client, plan_id):
        """
        Fetches a :class:`models.Plan` object from the plan id

        :param plan_id: Plan ID to fetch from
        :return: :class:`models.Plan` object
        :rtype: models.Plan
        :raises: FBchatException if request failed
        """
        data = {"event_reminder_id": plan_id}
        j = Client._post(Client.req_url.PLAN_INFO, data, fix_request=True, as_json=True)
        plan = graphql_to_plan(j["payload"])
        return plan

    def FET__getPrivateData(self, Client):
        j = Client.graphql_request(GraphQL(doc_id="1868889766468115"))
        return j["viewer"]

    def FET_getPhoneNumbers(self, Client):
        """
        Fetches a list of user phone numbers.

        :return: List of phone numbers
        :rtype: list
        """
        data = Client._getPrivateData()
        return [
            j["phone_number"]["universal_number"] for j in data["user"]["all_phones"]
        ]

    def FET_getEmails(self, Client):
        """
        Fetches a list of user emails.

        :return: List of emails
        :rtype: list
        """
        data = Client._getPrivateData()
        return [j["display_email"] for j in data["all_emails"]]

    def FET_getUserActiveStatus(self, Client, user_id):
        """
        Gets friend active status as an :class:`models.ActiveStatus` object.
        Returns `None` if status isn't known.

        .. warning::
            Only works when listening.

        :param user_id: ID of the user
        :return: Given user active status
        :rtype: models.ActiveStatus
        """
        return Client._buddylist.get(str(user_id))

    """
    END FETCH METHODS
    """