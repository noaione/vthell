# VTHell Chat Downloader

Based on https://github.com/xenova/chat-downloader

This implementation is mostly the same but simplified more and support asyncio.

## How it will works?

It will works the same if you use chat-downloader normally, but it is specifically made to be used in asyncio tasks and can be cancelable easily.
It will use file streaming for writing with little to none cache on memory.

If you want to enable it, change the following line to `true`:

```yaml
# Enable or disable the chat downloader
VTHELL_CHAT_DOWNLOADER=true
```

## License

The original code is licensed with [MIT](https://github.com/xenova/chat-downloader/blob/master/LICENSE) and this code is also licensed with [MIT](https://github.com/noaione/vthell).