from __future__ import unicode_literals
from collections import OrderedDict
from ._util import *
from .graphql import *


class Sender(object):

    def __init__(self):
        pass

    """
    Sender class contains all of the functions used to send messages

    :dependencies are imported to assure original functionality 
    :functions are the original functions from _client.py with s_ at the beginning
    :this is done to avoid any conflict with the linker functions
    """

    def s_send(self, client, message, thread_id=None, thread_type=ThreadType.USER):
        """
        Sends a message to a thread

        :param client: fbchat Client to be used
        :param message: Message to send
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type message: models.Message
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent message
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = client._getThread(thread_id, thread_type)
        data = _get_send_data(client,
                              message=message, thread_id=thread_id, thread_type=thread_type
                              )

        return _do_send_request(client, data)

    def s_send_message(self, client, message, thread_id=None, thread_type=ThreadType.USER):
        """
        Deprecated. Use :func:`fbchat.Client.send` instead
        """
        return client.send(
            Message(text=message), thread_id=thread_id, thread_type=thread_type
        )

    def s_send_emoji(
            self,
            client,
            emoji=None,
            size=EmojiSize.SMALL,
            thread_id=None,
            thread_type=ThreadType.USER,
    ):
        """
        Deprecated. Use :func:`fbchat.Client.send` instead
        """
        return client.send(
            Message(text=emoji, emoji_size=size),
            thread_id=thread_id,
            thread_type=thread_type,
        )

    def s_wave(self, client, wave_first=True, thread_id=None, thread_type=None):
        """
        Says hello with a wave to a thread!

        :param client: fbchat Client to be used
        :param wave_first: Whether to wave first or wave back
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent message
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = client._getThread(thread_id, thread_type)
        data = _get_send_data(thread_id=thread_id, thread_type=thread_type)
        data["action_type"] = "ma-type:user-generated-message"
        data["lightweight_action_attachment[lwa_state]"] = (
            "INITIATED" if wave_first else "RECIPROCATED"
        )
        data["lightweight_action_attachment[lwa_type]"] = "WAVE"
        if thread_type == ThreadType.USER:
            data["specific_to_list[0]"] = "fbid:{}".format(thread_id)
        return _do_send_request(data)

    def s_quick_reply(self, client, quick_reply, payload=None, thread_id=None, thread_type=None):
        """
        Replies to a chosen quick reply

        :param client: fbchat Client to be used
        :param quick_reply: Quick reply to reply to
        :param payload: Optional answer to the quick reply
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type quick_reply: models.QuickReply
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent message
        :raises: FBchatException if request failed
        """
        quick_reply.is_response = True
        if isinstance(quick_reply, QuickReplyText):
            return client.send(
                Message(text=quick_reply.title, quick_replies=[quick_reply])
            )
        elif isinstance(quick_reply, QuickReplyLocation):
            if not isinstance(payload, LocationAttachment):
                raise ValueError(
                    "Payload must be an instance of `fbchat.models.LocationAttachment`"
                )
            return client.sendLocation(
                payload, thread_id=thread_id, thread_type=thread_type
            )
        elif isinstance(quick_reply, QuickReplyEmail):
            if not payload:
                payload = client.getEmails()[0]
            quick_reply.external_payload = quick_reply.payload
            quick_reply.payload = payload
            return client.send(Message(text=payload, quick_replies=[quick_reply]))
        elif isinstance(quick_reply, QuickReplyPhoneNumber):
            if not payload:
                payload = client.getPhoneNumbers()[0]
            quick_reply.external_payload = quick_reply.payload
            quick_reply.payload = payload
            return client.send(Message(text=payload, quick_replies=[quick_reply]))

    def s_unsend(self, client, mid):
        """
        Unsends a message (removes for everyone)

        :param client: fbchat Client to be used
        :param mid: :ref:`Message ID <intro_message_ids>` of the message to unsend
        """
        data = {"message_id": mid}
        r = client._post(client.req_url.UNSEND, data)
        r.raise_for_status()

    def s_send_location(self, client, location, thread_id=None, thread_type=None):
        """
        Sends a given location to a thread as the user's current location

        :param client: fbchat Client to be used
        :param location: Location to send
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type location: models.LocationAttachment
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent message
        :raises: FBchatException if request failed
        """
        _send_location(
            client,
            location=location,
            current=True,
            thread_id=thread_id,
            thread_type=thread_type,
        )

    def s_send_pinned_location(self, client, location, thread_id=None, thread_type=None):
        """
        Sends a given location to a thread as a pinned location

        :param client: fbchat Client to be used
        :param location: Location to send
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type location: models.LocationAttachment
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent message
        :raises: FBchatException if request failed
        """
        _send_location(
            client,
            location=location,
            current=False,
            thread_id=thread_id,
            thread_type=thread_type,
        )

    def s_send_remote_files(
            self, client, file_urls, message=None, thread_id=None, thread_type=ThreadType.USER
    ):
        """
        Sends files from URLs to a thread

        :param client: fbchat Client to be used
        :param file_urls: URLs of files to upload and send
        :param message: Additional message
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent files
        :raises: FBchatException if request failed
        """
        file_urls = require_list(file_urls)
        files = _upload(client, get_files_from_urls(file_urls))
        return _send_files(
            client, files=files, message=message, thread_id=thread_id, thread_type=thread_type
        )

    def s_send_local_files(
            self, client, file_paths, message=None, thread_id=None, thread_type=ThreadType.USER
    ):
        """
        Sends local files to a thread

        :param client: fbchat Client to be used
        :param file_paths: Paths of files to upload and send
        :param message: Additional message
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent files
        :raises: FBchatException if request failed
        """
        file_paths = require_list(file_paths)
        with get_files_from_paths(file_paths) as x:
            files = _upload(client, x)
        return _send_files(
            client, files=files, message=message, thread_id=thread_id, thread_type=thread_type
        )

    def s_send_remote_voice_clips(
            self, client, clip_urls, message=None, thread_id=None, thread_type=ThreadType.USER
    ):
        """
        Sends voice clips from URLs to a thread

        :param client: fbchat Client to be used
        :param clip_urls: URLs of clips to upload and send
        :param message: Additional message
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent files
        :raises: FBchatException if request failed
        """
        clip_urls = require_list(clip_urls)
        files = _upload(client, get_files_from_urls(clip_urls), voice_clip=True)
        return _send_files(
            client, files=files, message=message, thread_id=thread_id, thread_type=thread_type
        )

    def s_send_local_voice_clips(
            self, client, clip_paths, message=None, thread_id=None, thread_type=ThreadType.USER
    ):
        """
        Sends local voice clips to a thread

        :param client: fbchat Client to be used
        :param clip_paths: Paths of clips to upload and send
        :param message: Additional message
        :param thread_id: User/Group ID to send to. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :return: :ref:`Message ID <intro_message_ids>` of the sent files
        :raises: FBchatException if request failed
        """
        clip_paths = require_list(clip_paths)
        with get_files_from_paths(clip_paths) as x:
            files = _upload(client, x, voice_clip=True)
        return _send_files(
            client, files=files, message=message, thread_id=thread_id, thread_type=thread_type
        )

    def s_send_image(
            self,
            client,
            image_id,
            message=None,
            thread_id=None,
            thread_type=ThreadType.USER,
            is_gif=False,
    ):
        """
        Deprecated. Use :func:`fbchat.Client._sendFiles` instead
        """
        if is_gif:
            return _send_files(
                client,
                files=[(image_id, "image/png")],
                message=message,
                thread_id=thread_id,
                thread_type=thread_type,
            )
        else:
            return _send_files(
                client,
                files=[(image_id, "image/gif")],
                message=message,
                thread_id=thread_id,
                thread_type=thread_type,
            )

    def s_send_remote_image(
            self, client, image_url, message=None, thread_id=None, thread_type=ThreadType.USER
    ):
        """
        Deprecated. Use :func:`fbchat.Client.sendRemoteFiles` instead
        """
        return client.sendRemoteFiles(
            file_urls=[image_url],
            message=message,
            thread_id=thread_id,
            thread_type=thread_type,
        )

    def s_send_local_image(
            self, client, image_path, message=None, thread_id=None, thread_type=ThreadType.USER
    ):
        """
        Deprecated. Use :func:`fbchat.Client.sendLocalFiles` instead
        """
        return client.sendLocalFiles(
            file_paths=[image_path],
            message=message,
            thread_id=thread_id,
            thread_type=thread_type,
        )

    def s_create_group(self, client, message, user_ids):
        """
        Creates a group with the given ids

        :param client: fbchat Client to be used
        :param message: The initial message
        :param user_ids: A list of users to create the group with.
        :return: ID of the new group
        :raises: FBchatException if request failed
        """
        data = _get_send_data(message=_old_message(message))

        if len(user_ids) < 2:
            raise FBchatUserError("Error when creating group: Not enough participants")

        for i, user_id in enumerate(user_ids + [client.uid]):
            data["specific_to_list[{}]".format(i)] = "fbid:{}".format(user_id)

        message_id, thread_id = _do_send_request(data, get_thread_id=True)
        if not thread_id:
            raise FBchatException(
                "Error when creating group: No thread_id could be found"
            )
        return thread_id

    def s_add_users_to_group(self, client, user_ids, thread_id=None):
        """
        Adds users to a group.

        :param client: fbchat Client to be used
        :param user_ids: One or more user IDs to add
        :param thread_id: Group ID to add people to. See :ref:`intro_threads`
        :type user_ids: list
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = client._getThread(thread_id, None)
        data = _get_send_data(client, thread_id=thread_id, thread_type=ThreadType.GROUP)

        data["action_type"] = "ma-type:log-message"
        data["log_message_type"] = "log:subscribe"

        user_ids = require_list(user_ids)

        for i, user_id in enumerate(user_ids):
            if user_id == client.uid:
                raise FBchatUserError(
                    "Error when adding users: Cannot add client to group thread"
                )
            else:
                data[
                    "log_message_data[added_participants][" + str(i) + "]"
                    ] = "fbid:" + str(user_id)

        return _do_send_request(client, data)

    def s_remove_user_from_group(self, client, user_id, thread_id=None):
        """
        Removes users from a group.

        :param client: fbchat Client to be used
        :param user_id: User ID to remove
        :param thread_id: Group ID to remove people from. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """

        thread_id, thread_type = client._getThread(thread_id, None)

        data = {"uid": user_id, "tid": thread_id}

        j = client._post(client.req_url.REMOVE_USER, data, fix_request=True, as_json=True)

    def s_add_group_admins(self, client, admin_ids, thread_id=None):
        """
        Sets specifed users as group admins.

        :param client: fbchat Client to be used
        :param admin_ids: One or more user IDs to set admin
        :param thread_id: Group ID to remove people from. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        _admin_status(admin_ids, True, thread_id)

    def s_remove_group_admins(self, client, admin_ids, thread_id=None):
        """
        Removes admin status from specifed users.

        :param client: fbchat Client to be used
        :param admin_ids: One or more user IDs to remove admin
        :param thread_id: Group ID to remove people from. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        _admin_status(client, admin_ids, False, thread_id)

    def s_change_group_approval_mode(self, client, require_admin_approval, thread_id=None):
        """
        Changes group's approval mode

        :param client: fbchat Client to be used
        :param require_admin_approval: True or False
        :param thread_id: Group ID to remove people from. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = client._getThread(thread_id, None)

        data = {"set_mode": int(require_admin_approval), "thread_fbid": thread_id}

        j = client._post(client.req_url.APPROVAL_MODE, data, fix_request=True, as_json=True)

    def s_accept_users_to_group(self, client, user_ids, thread_id=None):
        """
        Accepts users to the group from the group's approval

        :param client: fbchat Client to be used
        :param user_ids: One or more user IDs to accept
        :param thread_id: Group ID to accept users to. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        _users_approval(user_ids, True, thread_id)

    def s_deny_users_from_group(self, client, user_ids, thread_id=None):
        """
        Denies users from the group's approval

        :param client: fbchat Client to be used
        :param user_ids: One or more user IDs to deny
        :param thread_id: Group ID to deny users from. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        _users_approval(user_ids, False, thread_id)

    def s_change_group_image_remote(self, client, image_url, thread_id=None):
        """
        Changes a thread image from a URL

        :param client: fbchat Client to be used
        :param image_url: URL of an image to upload and change
        :param thread_id: User/Group ID to change image. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """

        (image_id, mimetype), = _upload(client, get_files_from_urls([image_url]))
        return _change_group_image(image_id, thread_id)

    def s_change_group_image_local(self, client, image_path, thread_id=None):
        """
        Changes a thread image from a local path

        :param client: fbchat Client to be used
        :param image_path: Path of an image to upload and change
        :param thread_id: User/Group ID to change image. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """

        with get_files_from_paths([image_path]) as files:
            (image_id, mimetype), = _upload(client, files)

        return _change_group_image(image_id, thread_id)

    def s_change_thread_title(self, client, title, thread_id=None, thread_type=ThreadType.USER):
        """
        Changes title of a thread.
        If this is executed on a user thread, this will change the nickname of that user, effectively changing the title

        :param client: fbchat Client to be used
        :param title: New group thread title
        :param thread_id: Group ID to change title of. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :raises: FBchatException if request failed
        """

        thread_id, thread_type = client._getThread(thread_id, thread_type)

        if thread_type == ThreadType.USER:
            # The thread is a user, so we change the user's nickname
            return client.changeNickname(
                title, thread_id, thread_id=thread_id, thread_type=thread_type
            )

        data = {"thread_name": title, "thread_id": thread_id}

        j = client._post(client.req_url.THREAD_NAME, data, fix_request=True, as_json=True)

    def s_change_nickname(
            self, client, nickname, user_id, thread_id=None, thread_type=ThreadType.USER
    ):
        """
        Changes the nickname of a user in a thread

        :param client: fbchat Client to be used
        :param nickname: New nickname
        :param user_id: User that will have their nickname changed
        :param thread_id: User/Group ID to change color of. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = client._getThread(thread_id, thread_type)

        data = {
            "nickname": nickname,
            "participant_id": user_id,
            "thread_or_other_fbid": thread_id,
        }

        j = client._post(
            client.req_url.THREAD_NICKNAME, data, fix_request=True, as_json=True
        )

    def s_change_thread_color(self, client, color, thread_id=None):
        """
        Changes thread color

        :param client: fbchat Client to be used
        :param color: New thread color
        :param thread_id: User/Group ID to change color of. See :ref:`intro_threads`
        :type color: models.ThreadColor
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = client._getThread(thread_id, None)

        data = {
            "color_choice": color.value if color != ThreadColor.MESSENGER_BLUE else "",
            "thread_or_other_fbid": thread_id,
        }

        j = client._post(client.req_url.THREAD_COLOR, data, fix_request=True, as_json=True)

    def s_change_thread_emoji(self, client, emoji, thread_id=None):
        """
        Changes thread color

        Trivia: While changing the emoji, the Facebook web client actually sends multiple different requests, though
        only this one is required to make the change

        :param client: fbchat Client to be used
        :param color: New thread emoji
        :param thread_id: User/Group ID to change emoji of. See :ref:`intro_threads`
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = client._getThread(thread_id, None)

        data = {"emoji_choice": emoji, "thread_or_other_fbid": thread_id}

        j = client._post(client.req_url.THREAD_EMOJI, data, fix_request=True, as_json=True)

    def s_react_to_message(self, client, message_id, reaction):
        """
        Reacts to a message, or removes reaction

        :param client: fbchat Client to be used
        :param message_id: :ref:`Message ID <intro_message_ids>` to react to
        :param reaction: Reaction emoji to use, if None removes reaction
        :type reaction: models.MessageReaction or None
        :raises: FBchatException if request failed
        """
        data = {
            "doc_id": 1491398900900362,
            "variables": json.dumps(
                {
                    "data": {
                        "action": "ADD_REACTION" if reaction else "REMOVE_REACTION",
                        "client_mutation_id": "1",
                        "actor_id": client.uid,
                        "message_id": str(message_id),
                        "reaction": reaction.value if reaction else None,
                    }
                }
            ),
        }
        client._post(client.req_url.MESSAGE_REACTION, data, fix_request=True, as_json=True)

    def s_create_plan(self, client, plan, thread_id=None):
        """
        Sets a plan

        :param client: fbchat Client to be used
        :param plan: Plan to set
        :param thread_id: User/Group ID to send plan to. See :ref:`intro_threads`
        :type plan: models.Plan
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = client._getThread(thread_id, None)

        full_data = {
            "event_type": "EVENT",
            "event_time": plan.time,
            "title": plan.title,
            "thread_id": thread_id,
            "location_id": plan.location_id or "",
            "location_name": plan.location or "",
            "acontext": {
                "action_history": [
                    {"surface": "messenger_chat_tab", "mechanism": "messenger_composer"}
                ]
            },
        }

        j = client._post(
            client.req_url.PLAN_CREATE, full_data, fix_request=True, as_json=True
        )

    def s_edit_plan(self, client, plan, new_plan):
        """
        Edits a plan

        :param client: fbchat Client to be used
        :param plan: Plan to edit
        :param new_plan: New plan
        :type plan: models.Plan
        :raises: FBchatException if request failed
        """
        full_data = {
            "event_reminder_id": plan.uid,
            "delete": "false",
            "date": new_plan.time,
            "location_name": new_plan.location or "",
            "location_id": new_plan.location_id or "",
            "title": new_plan.title,
            "acontext": {
                "action_history": [
                    {"surface": "messenger_chat_tab", "mechanism": "reminder_banner"}
                ]
            },
        }

        j = client._post(
            client.req_url.PLAN_CHANGE, full_data, fix_request=True, as_json=True
        )

    def s_delete_plan(self, client, plan):
        """
        Deletes a plan

        :param client: fbchat Client to be used
        :param plan: Plan to delete
        :raises: FBchatException if request failed
        """
        full_data = {
            "event_reminder_id": plan.uid,
            "delete": "true",
            "acontext": {
                "action_history": [
                    {"surface": "messenger_chat_tab", "mechanism": "reminder_banner"}
                ]
            },
        }

        j = client._post(
            client.req_url.PLAN_CHANGE, full_data, fix_request=True, as_json=True
        )

    def s_change_plan_participation(self, client, plan, take_part=True):
        """
        Changes participation in a plan

        :param client: fbchat Client to be used
        :param plan: Plan to take part in or not
        :param take_part: Whether to take part in the plan
        :raises: FBchatException if request failed
        """
        full_data = {
            "event_reminder_id": plan.uid,
            "guest_state": "GOING" if take_part else "DECLINED",
            "acontext": {
                "action_history": [
                    {"surface": "messenger_chat_tab", "mechanism": "reminder_banner"}
                ]
            },
        }

        j = client._post(
            client.req_url.PLAN_PARTICIPATION, full_data, fix_request=True, as_json=True
        )

    def s_event_reminder(self, client, thread_id, time, title, location="", location_id=""):
        """
        Deprecated. Use :func:`fbchat.Client.createPlan` instead
        """
        client.createPlan(
            plan=Plan(
                time=time, title=title, location=location, location_id=location_id
            ),
            thread_id=thread_id,
        )

    def s_create_poll(self, client, poll, thread_id=None):
        """
        Creates poll in a group thread

        :param client: fbchat Client to be used
        :param poll: Poll to create
        :param thread_id: User/Group ID to create poll in. See :ref:`intro_threads`
        :type poll: models.Poll
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = client._getThread(thread_id, None)

        # We're using ordered dicts, because the Facebook endpoint that parses the POST
        # parameters is badly implemented, and deals with ordering the options wrongly.
        # This also means we had to change `client.payloadDefault` to an ordered dict,
        # since that's being copied in between this point and the `requests` call
        #
        # If you can find a way to fix this for the endpoint, or if you find another
        # endpoint, please do suggest it ;)
        data = OrderedDict([("question_text", poll.title), ("target_id", thread_id)])

        for i, option in enumerate(poll.options):
            data["option_text_array[{}]".format(i)] = option.text
            data["option_is_selected_array[{}]".format(i)] = str(int(option.vote))

        j = client._post(client.req_url.CREATE_POLL, data, fix_request=True, as_json=True)

    def s_update_poll_vote(self, client, poll_id, option_ids=[], new_options=[]):
        """
        Updates a poll vote

        :param client: fbchat Client to be used
        :param poll_id: ID of the poll to update vote
        :param option_ids: List of the option IDs to vote
        :param new_options: List of the new option names
        :param thread_id: User/Group ID to change status in. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type thread_type: models.ThreadType
        :raises: FBchatException if request failed
        """
        data = {"question_id": poll_id}

        for i, option_id in enumerate(option_ids):
            data["selected_options[{}]".format(i)] = option_id

        for i, option_text in enumerate(new_options):
            data["new_options[{}]".format(i)] = option_text

        j = client._post(client.req_url.UPDATE_VOTE, data, fix_request=True, as_json=True)

    def s_set_typing_status(self, client, status, thread_id=None, thread_type=None):
        """
        Sets users typing status in a thread

        :param client: fbchat Client to be used
        :param status: Specify the typing status
        :param thread_id: User/Group ID to change status in. See :ref:`intro_threads`
        :param thread_type: See :ref:`intro_threads`
        :type status: models.TypingStatus
        :type thread_type: models.ThreadType
        :raises: FBchatException if request failed
        """
        thread_id, thread_type = client._getThread(thread_id, thread_type)

        data = {
            "typ": status.value,
            "thread": thread_id,
            "to": thread_id if thread_type == ThreadType.USER else "",
            "source": "mercury-chat",
        }

        j = client._post(client.req_url.TYPING, data, fix_request=True, as_json=True)


def _old_message(message):
    return message if isinstance(message, Message) else Message(text=message)


def _get_send_data(client, message=None, thread_id=None, thread_type=ThreadType.USER):
    """Returns the data needed to send a request to `SendURL`"""
    messageAndOTID = generateOfflineThreadingID()
    timestamp = now()
    data = {
        "client": client.client,
        "author": "fbid:" + str(client.uid),
        "timestamp": timestamp,
        "source": "source:chat:web",
        "offline_threading_id": messageAndOTID,
        "message_id": messageAndOTID,
        "threading_id": generateMessageID(client.client_id),
        "ephemeral_ttl_mode:": "0",
    }

    # Set recipient
    if thread_type in [ThreadType.USER, ThreadType.PAGE]:
        data["other_user_fbid"] = thread_id
    elif thread_type == ThreadType.GROUP:
        data["thread_fbid"] = thread_id

    if message is None:
        message = Message()

    if message.text or message.sticker or message.emoji_size:
        data["action_type"] = "ma-type:user-generated-message"

    if message.text:
        data["body"] = message.text

    for i, mention in enumerate(message.mentions):
        data["profile_xmd[{}][id]".format(i)] = mention.thread_id
        data["profile_xmd[{}][offset]".format(i)] = mention.offset
        data["profile_xmd[{}][length]".format(i)] = mention.length
        data["profile_xmd[{}][type]".format(i)] = "p"

    if message.emoji_size:
        if message.text:
            data["tags[0]"] = "hot_emoji_size:" + message.emoji_size.name.lower()
        else:
            data["sticker_id"] = message.emoji_size.value

    if message.sticker:
        data["sticker_id"] = message.sticker.uid

    if message.quick_replies:
        xmd = {"quick_replies": []}
        for quick_reply in message.quick_replies:
            q = dict()
            q["content_type"] = quick_reply._type
            q["payload"] = quick_reply.payload
            q["external_payload"] = quick_reply.external_payload
            q["data"] = quick_reply.data
            if quick_reply.is_response:
                q["ignore_for_webhook"] = False
            if isinstance(quick_reply, QuickReplyText):
                q["title"] = quick_reply.title
            if not isinstance(quick_reply, QuickReplyLocation):
                q["image_url"] = quick_reply.image_url
            xmd["quick_replies"].append(q)
        if len(message.quick_replies) == 1 and message.quick_replies[0].is_response:
            xmd["quick_replies"] = xmd["quick_replies"][0]
        data["platform_xmd"] = json.dumps(xmd)

    return data


def _do_send_request(client, data, get_thread_id=False):
    """Sends the data to `SendURL`, and returns the message ID or None on failure"""
    j = client._post(client.req_url.SEND, data, fix_request=True, as_json=True)

    # update JS token if received in response
    fb_dtsg = get_jsmods_require(j, 2)
    if fb_dtsg is not None:
        client.payloadDefault["fb_dtsg"] = fb_dtsg

    try:
        message_ids = [
            (action["message_id"], action["thread_fbid"])
            for action in j["payload"]["actions"]
            if "message_id" in action
        ]
        if len(message_ids) != 1:
            log.warning("Got multiple message ids' back: {}".format(message_ids))
        if get_thread_id:
            return message_ids[0]
        else:
            return message_ids[0][0]
    except (KeyError, IndexError, TypeError) as e:
        raise FBchatException(
            "Error when sending message: No message IDs could be found: {}".format(
                j
            )
        )


def _send_location(client, location, current=True, thread_id=None, thread_type=None):
    thread_id, thread_type = client._getThread(thread_id, thread_type)
    data = _get_send_data(client, thread_id=thread_id, thread_type=thread_type)
    data["action_type"] = "ma-type:user-generated-message"
    data["location_attachment[coordinates][latitude]"] = location.latitude
    data["location_attachment[coordinates][longitude]"] = location.longitude
    data["location_attachment[is_current_location]"] = current
    return _do_send_request(client, data)


def _upload(client, files, voice_clip=False):
    """
    Uploads files to Facebook

    `files` should be a list of files that requests can upload, see:
    http://docs.python-requests.org/en/master/api/#requests.request

    Returns a list of tuples with a file's ID and mimetype
    """
    file_dict = {"upload_{}".format(i): f for i, f in enumerate(files)}

    data = {"voice_clip": voice_clip}

    j = client._postFile(
        client.req_url.UPLOAD,
        files=file_dict,
        query=data,
        fix_request=True,
        as_json=True,
    )

    if len(j["payload"]["metadata"]) != len(files):
        raise FBchatException(
            "Some files could not be uploaded: {}, {}".format(j, files)
        )

    return [
        (data[mimetype_to_key(data["filetype"])], data["filetype"])
        for data in j["payload"]["metadata"]
    ]


def _send_files(client, files, message=None, thread_id=None, thread_type=ThreadType.USER):
    """
    Sends files from file IDs to a thread

    `files` should be a list of tuples, with a file's ID and mimetype
    """
    thread_id, thread_type = client._getThread(thread_id, thread_type)
    data = _get_send_data(
        client,
        message=_old_message(message),
        thread_id=thread_id,
        thread_type=thread_type,
    )

    data["action_type"] = "ma-type:user-generated-message"
    data["has_attachment"] = True

    for i, (file_id, mimetype) in enumerate(files):
        data["{}s[{}]".format(mimetype_to_key(mimetype), i)] = file_id

    return _do_send_request(client, data)


def _admin_status(self, client, admin_ids, admin, thread_id=None):
    thread_id, thread_type = client._getThread(thread_id, None)

    data = {"add": admin, "thread_fbid": thread_id}

    admin_ids = require_list(admin_ids)

    for i, admin_id in enumerate(admin_ids):
        data["admin_ids[" + str(i) + "]"] = str(admin_id)

    j = client._post(client.req_url.SAVE_ADMINS, data, fix_request=True, as_json=True)


def _users_approval(self, client, user_ids, approve, thread_id=None):
    thread_id, thread_type = client._getThread(thread_id, None)

    user_ids = list(require_list(user_ids))

    j = client.graphql_request(
        GraphQL(
            doc_id="1574519202665847",
            params={
                "data": {
                    "client_mutation_id": "0",
                    "actor_id": client.uid,
                    "thread_fbid": thread_id,
                    "user_ids": user_ids,
                    "response": "ACCEPT" if approve else "DENY",
                    "surface": "ADMIN_MODEL_APPROVAL_CENTER",
                }
            },
        )
    )


def _change_group_image(self, client, image_id, thread_id=None):
    """
    Changes a thread image from an image id

    :param client: fbchat Client to be used
    :param image_id: ID of uploaded image
    :param thread_id: User/Group ID to change image. See :ref:`intro_threads`
    :raises: FBchatException if request failed
    """

    thread_id, thread_type = client._getThread(thread_id, None)

    data = {"thread_image_id": image_id, "thread_id": thread_id}

    j = client._post(client.req_url.THREAD_IMAGE, data, fix_request=True, as_json=True)
    return image_id
