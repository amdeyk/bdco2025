# Understanding Application Logs

This project uses `uvicorn` and the Python `logging` module. Each line in the logs generally follows the format:

```
<timestamp> - <logger name> - <LEVEL> - <message>
```

For example:

```
2025-06-06 04:13:21,767 - app.routes.admin - INFO - Admin admin accessing guest details for ID: 4BD96189
```

* `2025-06-06 04:13:21,767` – Date and time of the log.
* `app.routes.admin` – The module that produced the message.
* `INFO` – The log level (`INFO`, `ERROR`, etc.).
* The rest of the line is the log message itself.

### HTTP request logs

Lines that look like:

```
INFO:     106.221.229.76:0 - "GET /admin/dashboard HTTP/1.0" 200 OK
```

come from `uvicorn` and show HTTP requests. They include the client IP, HTTP method and path, and the response status code.

### Error example

```
2025-06-06 04:13:48,378 - app.services.email - ERROR - Error sending email: [Errno -2] Name or service not known
```

This indicates an error inside the email service. `[Errno -2] Name or service not known` means that the SMTP server configured in `email_config.ini` could not be resolved. Update `SMTPServer` to a valid host.
