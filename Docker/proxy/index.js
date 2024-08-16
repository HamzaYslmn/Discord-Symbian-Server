const express = require('express');
const axios = require('axios');
const FormData = require('form-data');
const multer = require('multer')
const path = require('path');

const storage = multer.memoryStorage()
const upload = multer({ storage: storage })

const EmojiConvertor = require('emoji-js');
const emoji = new EmojiConvertor();
emoji.replace_mode = 'unified';

const app = express();
app.use(express.static(path.join(__dirname, 'static')));
app.use(defaultContentType);
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const PORT = 8080;
const BASE = "/api/v9";
const DEST_BASE = "https://discord.com/api/v9";

// ID -> username mapping cache (used for parsing mentions)
const userCache = new Map();
const channelCache = new Map();
const CACHE_SIZE = 10000;

function handleError(res, e) {
    if (e.response) {
        console.log(e.response);
        res.status(e.response.status).send(e.response.data ?? e.response.statusText);
    } else {
        console.log(e);
        res.status(500).send('Proxy error');
    }
}

function stringifyUnicode(obj) {
    return JSON.stringify(obj)
        .replace(/[\u007F-\uFFFF]/g, (match) => {
            return '\\u' + ('0000' + match.charCodeAt(0).toString(16)).slice(-4);
        });
}

function defaultContentType(req, res, next) {
    if (req.headers["content-type"] === undefined || !req.headers["content-type"].startsWith("multipart/form-data")) {
        req.headers["content-type"] = "application/json";
    }
    next();
}

function getToken(req, res, next) {
    let token;

    if (req.query?.token) {
        token = req.query.token;
    }
    else if (req.headers?.authorization) {
        token = req.headers.authorization;
    }
    else if (req.body?.token) {
        token = req.body.token;
        delete req.body.token;
    }

    res.locals.headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Authorization": token,
        "X-Discord-Locale": "en-GB",
        "X-Debug-Options": "bugReporterEnabled",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    };
    next();
}

function parseMessageContent(content) {
    let result = content
        // try to convert <@12345...> format into @username
        .replace(/<@(\d{15,})>/gm, (mention, id) => {
            if (userCache.has(id)) return `@${userCache.get(id)}`;
            else return mention;
        })
        // try to convert <#12345...> format into #channelname
        .replace(/<#(\d{15,})>/gm, (mention, id) => {
            if (channelCache.has(id)) return `#${channelCache.get(id)}`;
            else return mention;
        })
        // replace <:name:12345...> emoji format with :name:
        .replace(/<a?(:\w*:)\d{15,}>/gm, "$1")

    // Replace Unicode emojis with :name: textual representations
    emoji.colons_mode = true;
    result = emoji.replace_unified(result);

    return result;
}

// Get servers
app.get(`${BASE}/users/@me/guilds`, getToken, async (req, res) => {
    try {
        const response = await axios.get(
            `${DEST_BASE}/users/@me/guilds`,
            {headers: res.locals.headers}
        );
        const guilds = response.data.map(g => {
            const result = {id: g.id, name: g.name};
            if (g.icon != null) result.icon = g.icon;
            return result;
        })
        res.send(stringifyUnicode(guilds));
    }
    catch (e) { handleError(res, e); }
});

// Get server channels
app.get(`${BASE}/guilds/:guild/channels`, getToken, async (req, res) => {
    try {
        const response = await axios.get(
            `${DEST_BASE}/guilds/${req.params.guild}/channels`,
            {headers: res.locals.headers}
        )

        // Populate channel name cache
        response.data.forEach(ch => {
            channelCache.set(ch.id, ch.name);

            // If max size exceeded, remove the oldest item
            if (channelCache.size > CACHE_SIZE) {
                channelCache.delete(channelCache.keys().next().value);
            }
        })

        const channels = response.data
            .filter(ch => ch.type == 0 || ch.type == 5)
            .map(ch => {
                return {
                    id: ch.id,
                    type: ch.type,
                    guild_id: ch.guild_id,
                    name: ch.name,
                    position: ch.position,
                    last_message_id: ch.last_message_id
                }
            });
        res.send(stringifyUnicode(channels));
    }
    catch (e) { handleError(res, e); }
});

// File upload form
app.get(`/upload`, async (req, res) => {
    try {
        if (!req.query?.channel || !req.query?.token) {
            res.send(`<p>Token or destination channel not defined</p>`);
        }

        res.send(
`<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload</title>
</head>
<body>
    <h1>Upload file</h1>
    <form method="post" enctype="multipart/form-data" action="${BASE}/channels/${req.query.channel}/upload">
        <input type="hidden" name="token" value="${req.query.token}" />

        <label for="file">File:</label><br />
        <input type="file" name="files" id="files"></input><br />

        <label for="content">Text:</label><br />
        <textarea name="content" id="content"></textarea><br />

        <input type="submit" value="Upload" />
    </form>
</body>
</html>`
        );
    }
    catch (e) { handleError(res, e); }
});

// Get DM channels
app.get(`${BASE}/users/@me/channels`, getToken, async (req, res) => {
    try {
        const response = await axios.get(
            `${DEST_BASE}/users/@me/channels`,
            {headers: res.locals.headers}
        );
        const channels = response.data
            .filter(ch => ch.type == 1 || ch.type == 3)
            .map(ch => {
                const result = {
                    id: ch.id,
                    type: ch.type,
                    last_message_id: ch.last_message_id
                }

                // Add name and icon for group DMs, recipient name and avatar for normal DMs
                if (ch.type == 3) {
                    result.name = ch.name;
                    if (ch.icon != null) result.icon = ch.icon;
                } else {
                    result.recipients = [{
                        global_name: ch.recipients[0].global_name,
                    }];

                    if (ch.recipients[0].avatar != null) {
                        result.recipients[0].id = ch.recipients[0].id;
                        result.recipients[0].avatar = ch.recipients[0].avatar;
                    }
                    if (ch.recipients[0].global_name == null) {
                        result.recipients[0].username = ch.recipients[0].username;
                    }
                }
                return result;
            })
        res.send(stringifyUnicode(channels));
    }
    catch (e) { handleError(res, e); }
});

// Get messages
app.get(`${BASE}/channels/:channel/messages`, getToken, async (req, res) => {
    try {
        let proxyUrl = `${DEST_BASE}/channels/${req.params.channel}/messages`;
        let queryParam = [];
        if (req.query.limit) queryParam.push(`limit=${req.query.limit}`);
        if (req.query.before) queryParam.push(`before=${req.query.before}`);
        if (req.query.after) queryParam.push(`after=${req.query.after}`);
        if (queryParam.length) proxyUrl += '?' + queryParam.join('&');

        const response = await axios.get(proxyUrl, {headers: res.locals.headers});

        // Populate username cache
        response.data.forEach(msg => {
            userCache.set(msg.author.id, msg.author.username);

            // If max size exceeded, remove the oldest item
            if (userCache.size > CACHE_SIZE) {
                userCache.delete(userCache.keys().next().value);
            }
        })

        const messages = response.data.map(msg => {
            const result = {
                id: msg.id,
                author: {
                    id: msg.author.id,
                    avatar: msg.author.avatar,
                    global_name: msg.author.global_name
                }
            }
            if (msg.author.global_name == null || req.query.droidcord) {
                result.author.username = msg.author.username;
            }
            if (msg.type >= 1 && msg.type <= 11) result.type = msg.type;

            // Parse content 
            if (msg.content) {
                result.content = parseMessageContent(msg.content);
                if (result.content != msg.content) result._rc = msg.content;
            }

            if (msg.referenced_message) {
                let content = parseMessageContent(msg.referenced_message.content);
                if (content && content.length > 50) {
                    content = content.slice(0, 47).trim() + '...';
                }
                result.referenced_message = {
                    author: {
                        global_name: msg.referenced_message.author.global_name,
                        id: msg.referenced_message.author.id,
                        avatar: msg.referenced_message.author.avatar
                    },
                    content
                }
                if (msg.referenced_message.author.global_name == null || req.query.droidcord) {
                    result.referenced_message.author.username =
                        msg.referenced_message.author.username;
                }
            }

            if (msg.attachments?.length) {
                result.attachments = msg.attachments
                    .map(att => {
                        var ret = {
                            filename: att.filename,
                            size: att.size,
                            width: att.width,
                            height: att.height,
                            proxy_url: att.proxy_url
                        };
                        if (req.query.droidcord) {
                            ret.content_type = att.content_type;
                        }
                        return ret;
                    })
            }
            if (msg.sticker_items?.length) {
                result.sticker_items = [{name: msg.sticker_items[0].name}];
            }
            if (msg.embeds?.length) {
                result.embeds = msg.embeds.map(emb => {
                    var ret = {
                        title: emb.title,
                        description: emb.description
                    };
                    if (req.query.droidcord) {
                        ret.url = emb.url;
                        ret.author = emb.author;
                        ret.provider = emb.provider;
                        ret.footer = emb.footer;
                        ret.timestamp = emb.timestamp;
                        ret.color = emb.color;
                        ret.thumbnail = emb.thumbnail;
                        ret.image = emb.image;
                        ret.video = emb.video;
                        ret.fields = emb.fields;
                    }
                    return ret;
                })
            }

            // Need first mentioned user for group DM join/leave notification messages
            if ((msg.type == 1 || msg.type == 2) && msg.mentions.length) {
                result.mentions = [
                    {
                        id: msg.mentions[0].id,
                        global_name: msg.mentions[0].global_name
                    }
                ]
                if (msg.mentions[0].global_name == null) {
                    result.mentions[0].username = msg.mentions[0].username;
                }
            }

            return result;
        })
        res.send(stringifyUnicode(messages));
    }
    catch (e) { handleError(res, e); }
});

// Send message
app.post(`${BASE}/channels/:channel/messages`, getToken, async (req, res) => {
    try {
        await axios.post(
            `${DEST_BASE}/channels/${req.params.channel}/messages`,
            req.body,
            {headers: res.locals.headers}
        );
        res.send("ok");
    }
    catch (e) { handleError(res, e); }
});

// Send message with attachments
app.post(`${BASE}/channels/:channel/upload`, upload.single('files'), getToken, async (req, res) => {
    try {
        const form = new FormData();
        let text = "Message sent!";

        if (req.file != null) {
            const options = {
                header: `\r\n--${form.getBoundary()}\r\nContent-Disposition: form-data; name="files[0]"; filename="${req.file.originalname}"\r\nContent-Type: ${req.file.mimetype}\r\n\r\n`
            };
            form.append('files[0]', req.file.buffer, options);
            text = "File sent!"
        }
        if (req.body) form.append('content', req.body.content);

        await axios.post(
            `${DEST_BASE}/channels/${req.params.channel}/messages`,
            form,
            {headers: res.locals.headers}
        )

        res.send(
            `<p>${text}</p><a href="/upload?channel=${req.params.channel}&token=${res.locals.headers.Authorization}">Send another</a>`
        );
    }
    catch (e) { handleError(res, e); }
});

// Mark message as read
app.post(`${BASE}/channels/:channel/messages/:message/ack`, getToken, async (req, res) => {
    try {
        await axios.post(
            `${DEST_BASE}/channels/${req.params.channel}/messages/${req.params.message}/ack`,
            req.body,
            {headers: res.locals.headers}
        );
        res.send("ok");
    }
    catch (e) { handleError(res, e); }
});

// Get user info (only ID is used)
app.get(`${BASE}/users/@me`, getToken, async (req, res) => {
    try {
        const response = await axios.get(
            `${DEST_BASE}/users/@me`,
            {headers: res.locals.headers}
        );
        res.send(JSON.stringify({
            id: response.data.id,
            _liteproxy: true
        }));
    }
    catch (e) { handleError(res, e); }
});

// Get server member
app.get(`${BASE}/guilds/:guild/members/:member`, getToken, async (req, res) => {
    try {
        const response = await axios.get(
            `${DEST_BASE}/guilds/${req.params.guild}/members/${req.params.member}`,
            {headers: res.locals.headers}
        );
        const member = {
            user: response.data.user,
            roles: response.data.roles,
            joined_at: response.data.joined_at
        };
        if (response.data.nick != null) member.avatar = response.data.nick;
        if (response.data.avatar != null) member.avatar = response.data.avatar;
        if (response.data.permissions != null) member.permissions = response.data.permissions;
        res.send(stringifyUnicode(member));
    }
    catch (e) { handleError(res, e); }
});

// Edit message (non-standard because J2ME doesn't support PATCH method)
app.post(`${BASE}/channels/:channel/messages/:message/edit`, getToken, async (req, res) => {
    try {
        await axios.patch(
            `${DEST_BASE}/channels/${req.params.channel}/messages/${req.params.message}`,
            req.body,
            {headers: res.locals.headers}
        );
        res.send("ok");
    }
    catch (e) { handleError(res, e); }
});

// Delete message (non-standard because J2ME doesn't support DELETE method)
app.get(`${BASE}/channels/:channel/messages/:message/delete`, getToken, async (req, res) => {
    try {
        await axios.delete(
            `${DEST_BASE}/channels/${req.params.channel}/messages/${req.params.message}`,
            {headers: res.locals.headers}
        );
        res.send("ok");
    }
    catch (e) { handleError(res, e); }
});

// Get role list
app.get(`${BASE}/guilds/:guild/roles`, getToken, async (req, res) => {
    try {
        const response = await axios.get(
            `${DEST_BASE}/guilds/${req.params.guild}/roles`,
            {headers: res.locals.headers}
        );
        const roles = response.data
            .sort((a, b) => a.position - b.position)
            .map(r => {
                var ret = {
                    id: r.id,
                    color: r.color
                };
                if (req.query.droidcord) {
                    ret.name = r.name;
                    ret.position = r.position;
                    ret.permissions = r.permissions;
                }
                return ret;
            })
        
        res.send(stringifyUnicode(roles))
    }
    catch (e) { handleError(res, e); }
});

app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
