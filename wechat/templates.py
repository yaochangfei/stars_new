# !/usr/bin/python
# -*- coding:utf-8 -*-

# 被动文本消息模板
TEMPLATE_TXT_PASSIVE = u'''
    <xml>
        <ToUserName><![CDATA[{open_id}]]></ToUserName>
        <FromUserName><![CDATA[{service_id}]]></FromUserName>
        <CreateTime>{timestamp}</CreateTime>
        <MsgType><![CDATA[text]]></MsgType>
        <Content><![CDATA[{content}]]></Content>
        <MsgId>{msg_id}</MsgId>
    </xml>
'''

# 被动图文消息模板
TEMPLATE_PIC_TXT_PASSIVE = u'''
    <xml>
        <ToUserName>
            <![CDATA[{open_id}]]>
        </ToUserName>
        <FromUserName>
            <![CDATA[{service_id}]]>
        </FromUserName>
        <CreateTime>
            {timestamp}
        </CreateTime>
        <MsgType>
            <![CDATA[news]]>
        </MsgType>
        <ArticleCount>
            {article_count}
        </ArticleCount>
        <Articles>
            {articles}
        </Articles>
    </xml>
'''

# 被动图文消息文章模板
TEMPLATE_ARTICLE_PIC_TXT_PASSIVE = u'''
    <item>
        <Title>
            <![CDATA[{title}]]>
        </Title>
        <Description>
            <![CDATA[{description}]]>
        </Description>
        <PicUrl>
            <![CDATA[{pic_url}]]>
        </PicUrl>
        <Url>
            <![CDATA[{url}]]>
        </Url>
    </item>
'''
