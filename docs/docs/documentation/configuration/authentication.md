# Authentication

Viseron supports authenticating users using a username and password.

It is **disabled** by default and can be enabled by setting the `auth` key in the configuration for `webserver`

```yaml
webserver:
  auth:
```

:::warning

The implementation has not been audited by security experts.
If you plan to expose Viseron to the internet I suggest coupling it with alternate authentication methods as well, such as Cloudflare Access or a VPN.

:::

## Creating the first user

When first enabling authentication, an admin user has to be created.<br />
The frontend will redirect you to an <code>Onboarding</code> page to create the first user when you try to access the web interface.

TODO: Add screenshot

## Adding more users

At the moment there is no way to add more users through the web interface.
This will be added in a future release.

## Resetting the password

If you forget your password, you can reset it by deleting these files:

```shell
/config/.viseron/onboarding
/config/.viseron/auth
```

After a restart, Viseron will once again prompt you to create an admin user.
