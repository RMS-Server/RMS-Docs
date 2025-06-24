# RMS 管理文档
> 此文档意图帮助文档维护者了解文档的所有特性
## 概述
本文档采用Markdown语法，不会的可以找AI或者自己学 ~~（比如说重华）~~
## 特性
1. 本次 V 3.1.0 将所有文本、图片、文件下载交由后端API进行，因此请**务必遵守以下规范**以免出现bug

    - 在加载图片时，请使用`![<图片ID>](图片相对路径)`

        例如：图片在仓库中`/Assets/example.png`，则填写`![testimage](/Assets/example.png)`
    
        **一定不要**像之前一样直接写`https://docs.rms.net.cn/context/Assets/example.png`，会被返回403
    - 需要下载文件时，请**务必**将需要玩家下载的文件放到`/download`目录。在需要玩家点击下载的地方直接使用`[downloadtest](/downloadit.zip)`。不需要加路径！直接填写文件名即可。**不可以直接使用**`https://docs.rms.net.cn/context/download/downloadit.zip`！会返回403
2. 现在文档会根据玩家查看的页面动态更改URL，并且可以直接通过该URL一键打开该页面。原来通过`/?path=/xxx`的用法已被弃用！

## 其他
目前就是这些，如果有bug及时反馈