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

## Adding more users

To add more users, navigate to the `/settings/users` page in the web interface, and click on the `Add User` button.
<img
    src="/img/screenshots/Viseron-Settings-add-user-button.png"
    alt-text="Add User Button"
    width={600}
  />

This will open a modal where you can enter the information for the new user.

### Roles

Viseron supports different roles for users, allowing for varying levels of access and control.

- **Admin**: Full access to all settings and configurations.
- **Write**: Can perform delete operations, but cannot change settings.
- **Read**: Can only view the web interface, but cannot make any changes.

A users role can be changed at any time by clicking on the user on the `User Management` page.

### Assigning cameras

You can restrict users to only see certain cameras by assigning them to a user.
To do this, navigate to the `User Management` page, and click on the user you want to edit.

<img
    src="/img/screenshots/Viseron-Settings-user-assign-cameras.png"
    alt-text="Assign Cameras to User"
    width={600}
  />

## Resetting the password

### User password

Users cannot currently change their own passwords, it has to be done by an admin.
To reset a users password, navigate to the `User Management` page, and click on the user you want to edit.

Click on the `Change Password` button, and enter the new password in the modal that opens.

### Admin password

If you forget the password to your only admin account, you can reset it by deleting these files:

```shell
/config/.viseron/onboarding
/config/.viseron/auth
```

After a restart, Viseron will once again prompt you to create an admin user.

:::danger

Deleting these files will also delete all other users. A way to properly reset the admin password will be added in the future.

:::
