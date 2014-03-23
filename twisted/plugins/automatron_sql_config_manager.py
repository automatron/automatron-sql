from twisted.enterprise import adbapi
from twisted.internet import defer
from twisted.python import log
from zope.interface import implements, classProvides
from automatron.config import IConfigManager, IAutomatronConfigManagerFactory


class SqlConfigManager(object):
    classProvides(IAutomatronConfigManagerFactory)
    implements(IConfigManager)

    name = 'sql'

    def __init__(self, controller):
        self._db_config = dict(controller.config_file.items('database'))
        self._db_api_name = self._db_config.pop('dbapi')
        self.database = None

    def prepare(self):
        # Set up the database connection pool
        self.database = adbapi.ConnectionPool(self._dbapi_name, **self._db_config)

    def shutdown(self):
        if self.database:
            print self.database.close()

    @defer.inlineCallbacks
    def enumerate_servers(self):
        defer.returnValue([
            s[0]
            for s in (yield self.database.runQuery(
                '''
                    SELECT
                        DISTINCT server
                    FROM
                        config
                    WHERE
                        section = 'server'
                        AND server IS NOT NULL
                        AND channel IS NULL
                        AND key = 'hostname'
                        AND value IS NOT NULL
                '''
            ))
        ])

    @defer.inlineCallbacks
    def get_section(self, section, server, channel):
        q = """
            SELECT
                key,
                value,
                CASE
                    WHEN channel IS NOT NULL AND server IS NOT NULL THEN 3
                    WHEN channel IS NOT NULL THEN 2
                    WHEN server IS NOT NULL THEN 1
                    ELSE 0
                END AS relevance
            FROM
                config
            WHERE
                section = %s
                AND (server IS NULL OR server = %s)
                AND (channel IS NULL OR channel = %s)
            ORDER BY
                relevance ASC
        """
        result = yield self.database.runQuery(q, (section, server, channel))

        section = {}
        for key, val, relevance in result:
            section[key] = val

        defer.returnValue(section)

    def get_plugin_section(self, plugin, server, channel):
        return self.get_section('plugin.%s' % plugin.name, server, channel)

    def delete_section(self, section, server, channel):
        q = ["""
            DELETE
            FROM
                config
            WHERE
                section = %s
        """]
        params = [section]

        if server is None:
            q.append('AND server IS NULL')
        else:
            q.append('AND server = %s')
            params.append(server)

        if channel is None:
            q.append('AND channel IS NULL')
        else:
            q.append('AND channel = %s')
            params.append(channel)

        return self.database.runOperation(q, params)

    @defer.inlineCallbacks
    def get_value(self, section, server, channel, key):
        q = """
            SELECT
                value,
                CASE
                    WHEN channel IS NOT NULL AND server IS NOT NULL THEN 3
                    WHEN channel IS NOT NULL THEN 2
                    WHEN server IS NOT NULL THEN 1
                    ELSE 0
                END AS relevance
            FROM
                config
            WHERE
                section = %s
                AND (server IS NULL OR server = %s)
                AND (channel IS NULL OR channel = %s)
                AND key = %s
            ORDER BY
                relevance DESC
            LIMIT 1
        """
        result = yield self.database.runQuery(q, (section, server, channel, key))

        if result:
            defer.returnValue(result[0])
        else:
            defer.returnValue((None, None))

    def get_plugin_value(self, plugin, server, channel, key):
        return self.get_value('plugin.%s' % plugin.name, server, channel, key)

    @defer.inlineCallbacks
    def update_value(self, section, server, channel, key, new_value):
        _, relevance = yield self.get_value(section, server, channel, key)
        if relevance is not None:
            if relevance == 2:
                server = None
            elif relevance == 1:
                channel = None
            elif relevance == 0:
                server = channel = None

            q = ["""
                UPDATE
                    config
                SET
                    value = %s
                WHERE
                    section = %s
                    AND key = %s
            """]
            params = [new_value, section, key]

            if server is not None:
                q.append('AND server = %s')
                params.append(server)
            else:
                q.append('AND server IS NULL')

            if channel is not None:
                q.append('AND channel = %s')
                params.append(channel)
            else:
                q.append('AND channel IS NULL')
        else:
            q = ["""
                INSERT INTO
                    config
                    (
                        section,
                        server,
                        channel,
                        key,
                        value
                    )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
            """]
            params = [section, server, channel, key, new_value]

        yield self.database.runOperation(' '.join(q), params)

    def update_plugin_value(self, plugin, server, channel, key, new_value):
        return self.update_value('plugin.%s' % plugin.name, server, channel, key, new_value)

    def delete_value(self, section, server, channel, key):
        q = ["""
            DELETE
            FROM
                config
            WHERE
                section = %s
                AND key = %s
        """]
        params = [section, key]

        if server is None:
            q.append('AND server IS NULL')
        else:
            q.append('AND server = %s')
            params.append(server)

        if channel is None:
            q.append('AND channel IS NULL')
        else:
            q.append('AND channel = %s')
            params.append(channel)

        return self.database.runOperation(q, params)

    @defer.inlineCallbacks
    def get_username_by_hostmask(self, server, user):
        q = """
            SELECT
                value,
                CASE
                    WHEN server IS NOT NULL THEN 1
                    ELSE 0
                END AS relevance
            FROM
                config
            WHERE
                section = 'user.hostmask'
                AND (server IS NULL OR server = %s)
                AND %s LIKE key
            ORDER BY
                relevance
            LIMIT 1
        """
        result = yield self.database.runQuery(q, (server, user))
        if result:
            defer.returnValue(result[0])
        else:
            defer.returnValue((None, None))

    @defer.inlineCallbacks
    def get_role_by_username(self, server, channel, username):
        defer.returnValue((yield self.get_value('user.role', server, channel, username)))

    @defer.inlineCallbacks
    def get_permissions_by_role(self, role):
        permissions, _ = yield self.get_value('role.permissions', None, None, role)
        if permissions is None:
            defer.returnValue(None)

        permissions = [p.strip() for p in permissions.split(',')]
        defer.returnValue(permissions)

    @defer.inlineCallbacks
    def has_permission(self, server, channel, user, permission):
        username, username_rel = yield self.get_username_by_hostmask(server, user)
        if username is None:
            defer.returnValue(False)

        role, role_rel = yield self.get_role_by_username(server, channel, username)
        if role is None:
            defer.returnValue(False)

        if role_rel < username_rel:
            defer.returnValue(False)

        permissions = yield self.get_permissions_by_role(role)
        if permissions is None:
            defer.returnValue(False)

        defer.returnValue(bool({'*', permission} & set(permissions)))

    @defer.inlineCallbacks
    def get_user_preference(self, server, username, preference):
        value, _ = yield self.get_value('user.pref', server, username, preference)
        defer.returnValue(value)

    @defer.inlineCallbacks
    def update_user_preference(self, server, username, preference, value):
        q = """
            SELECT
                CASE
                    WHEN server IS NOT NULL THEN 1
                    ELSE 0
                END AS relevance
            FROM
                config
            WHERE
                section = 'user.email'
                AND (server IS NULL OR server = %s)
                AND key = %s
            ORDER BY
                relevance
            LIMIT 1
        """
        result = yield self.database.runQuery(q, (server, username))
        if not result:
            log.msg('Something went terribly wrong, username %s was not found' % username)
            return

        if result[0][0] == 0:
            server = None
        self.update_value('user.pref', server, username, preference, value)

