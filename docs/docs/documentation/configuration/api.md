# API

:::warning

The Viseron API is not yet documented, which makes it hard to work with at this point. You can still use the API, but you will have to figure out how it works by looking at the code and/or by observing the requests made by the web interface. If you have any questions, please reach out to us on GitHub.

:::

## REST API

### Authentication

When authentication is enabled in the `webserver` component, all requests to the REST API will require authentication.

To authenticate with the API, you need to provide a personal access token in the `Authorization` header of your requests. You can generate a personal access token from the `Profile` page in the web interface.

## WebSocket API

### Authentication

When authentication is enabled in the `webserver` component, all requests to the WebSocket API will require authentication.

When connecting to the WebSocket API, Viseron will send an authentication request to the client. The client must respond with a valid personal access token in order to authenticate. You can generate a personal access token from the `Profile` page in the web interface.

The handshake process is as follows:

1. Client connects to the WebSocket API endpoint (`ws://<viseron_host>:<viseron_port>/ws`).
2. Viseron sends an authentication request to the client.
   ```json
   {
     "type": "auth_required",
     "message": "Authentication required."
   }
   ```
3. Client responds with a personal access token.
   ```json
   {
     "type": "auth",
     "access_token": "<personal_access_token>"
   }
   ```
4. Viseron validates the token and responds with an authentication result.
   - If the token is valid:
   ````json
   {
     "type": "auth_ok",
     "message": "Authentication successful.",
     "system_information": {
       "version": "<viseron server version>",
       "git_commit": "<git commit hash>",
       "safe_mode": true/false,
     }
   }
   - If the token is invalid:
   ```json
   {
     "type": "auth_invalid",
     "message": "Invalid access token."
   }
   ````
