from symphony.bdk.core.extension import BdkAuthenticationAware, BdkApiClientFactoryAware, BdkExtensionServiceProvider
from symphony.bdk.core.service.user.user_util import extract_tenant_id
from symphony.bdk.gen.group_api.group_api import GroupApi
from symphony.bdk.gen.group_model.add_member import AddMember
from symphony.bdk.gen.group_model.create_group import CreateGroup
from symphony.bdk.gen.group_model.group_list import GroupList
from symphony.bdk.gen.group_model.member import Member
from symphony.bdk.gen.group_model.read_group import ReadGroup
from symphony.bdk.gen.group_model.sort_order import SortOrder
from symphony.bdk.gen.group_model.status import Status
from symphony.bdk.gen.group_model.update_group import UpdateGroup
from symphony.bdk.gen.group_model.upload_avatar import UploadAvatar
from symphony.bdk.gen.login_api.authentication_api import AuthenticationApi


class SymphonyGroupBdkExtension(BdkAuthenticationAware, BdkApiClientFactoryAware, BdkExtensionServiceProvider):
    """ Extension for Symphony Groups APIs
    """
    def __init__(self):
        self._api_client_factory = None
        self._bot_session = None

    def set_api_client_factory(self, api_client_factory):
        self._api_client_factory = api_client_factory

    def set_bot_session(self, bot_session):
        self._bot_session = bot_session

    def get_service(self):
        return SymphonyGroupService(self._api_client_factory, self._bot_session)


class SymphonyGroupService:
    """ Service class for managing Symphony Groups
    """
    def __init__(self, api_client_factory, session):
        self._api_client_factory = api_client_factory
        self._session = session
        self._oauth_session = OAuthSession(self._api_client_factory.get_login_client(), self._session)

        client = self._api_client_factory.get_client("/profile-manager")
        # to enable setting the authorization header defined in api_client.ApiClient.update_params_for_auth
        client.configuration.auth_settings = lambda: {
            "bearerAuth": {"in": "header", "type": "bearer", "key": "Authorization",
                           "value": "Bearer " + self._oauth_session.bearer_token()}}
        # needed for the x_symphony_host parameter to allow empty value
        client.configuration._disabled_client_side_validations = ["minLength"]
        self._group_api = GroupApi(client)

    async def insert_group(self, create_group: CreateGroup) -> ReadGroup:
        """Create a new group
        See: `Insert a new group <https://developers.symphony.com/restapi/reference/insertgroup>`_

        :param create_group: the details of the group to be created
        :return: the created group
        """
        return await self._group_api.insert_group(x_symphony_host="", create_group=create_group)

    async def list_groups(self, status: Status = None, before: str = None, after: str = None, limit: int = None,
                          sort_order: SortOrder = None) -> GroupList:
        """List groups of type SDL
        See: `List all groups of specified type <https://developers.symphony.com/restapi/reference/listgroups>`_

        :param status: filter by status, active or deleted. If not specified, both are returned
        :param before: NOT SUPPORTED YET, currently ignored.
        :param after: cursor that points to the end of the current page of data. If not present, the current page is
            the first page
        :param limit: maximum number of items to return
        :param sort_order: sorting direction of items (ordered by creation date)
        :return: the list of matching groups
        """
        kwargs = dict(x_symphony_host="", type_id="SDL")
        if status is not None:
            kwargs["status"] = status
        if before is not None:
            kwargs["before"] = before
        if after is not None:
            kwargs["after"] = after
        if limit is not None:
            kwargs["limit"] = limit
        if sort_order is not None:
            kwargs["sort_order"] = sort_order
        return await self._group_api.list_groups(**kwargs)

    async def update_group(self, if_match: str, group_id: str, update_group: UpdateGroup) -> ReadGroup:
        """Update an existing group
        See: `Update a group <https://developers.symphony.com/restapi/reference/updategroup>`_

        :param if_match: eTag of the group to be updated
        :param group_id: the ID of the group
        :param update_group: the group fields to be updated
        :return: the updated group
        """
        return await self._group_api.update_group(x_symphony_host="", if_match=if_match, group_id=group_id,
                                                  update_group=update_group)

    async def update_avatar(self, group_id: str, image: str) -> ReadGroup:
        """Update the group avatar
        See: `Update the group avatar <https://developers.symphony.com/restapi/reference/updateavatar>`_

        :param group_id: the ID of the group
        :param image: The avatar image for the user profile picture.
            The image must be a base64-encoded .jpg, .png, or .gif. Image size limit: 2 MB
        :return: the updated group
        """
        upload_avatar = UploadAvatar(image=image)
        return await self._group_api.update_avatar(x_symphony_host="", group_id=group_id, upload_avatar=upload_avatar)

    async def get_group(self, group_id: str) -> ReadGroup:
        """Retrieve a specific group
        See: `Retrieve a group <https://developers.symphony.com/restapi/reference/getgroup>`_

        :param group_id: the ID of the group to retrieve
        :return: the group details
        """
        return await self._group_api.get_group(x_symphony_host="", group_id=group_id)

    async def add_member_to_group(self, group_id: str, user_id: int) -> ReadGroup:
        """Add a new user to an existing group.
        See: `Add a new user to an existing group <https://developers.symphony.com/restapi/reference/addmembertogroup>`_

        :param group_id: the ID of the group in which to add the user
        :param user_id: The ID of the user to be added into the group
        :return: the updated group
        """
        member = Member(member_id=user_id, member_tenant=extract_tenant_id(user_id))
        return await self._group_api.add_member_to_group(x_symphony_host="", group_id=group_id,
                                                         add_member=AddMember(member=member))


class OAuthSession:
    """Used to handle the bearer token needed to call Groups endpoints.
    """
    def __init__(self, login_client, session):
        self._authentication_api = AuthenticationApi(login_client)
        self._session = session
        self._bearer_token = None

    async def refresh(self):
        """Refreshes internal Bearer authentication token from the bot sessionToken.
        """
        jwt_token = await self._authentication_api.idm_tokens_post(await self._session.session_token,
                                                                   scope="profile-manager")
        self._bearer_token = jwt_token.access_token

    def bearer_token(self):
        """Returns the bearer token
        """
        return self._bearer_token