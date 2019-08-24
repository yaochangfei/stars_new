# !/usr/bin/python
# -*- coding:utf-8 -*-


import re
from string import Template

from motorengine import DESC, ASC
from motorengine.stages import SkipStage, SortStage, MatchStage, CountStage
from motorengine.stages.limit_stage import LimitStage


class Paging(object):
    """
        __url
            The URL template of page request
        __item_count
            The number of items all
        __items_per_page
            The maximal number of items displayed on a page
        __first_page
            The number of the first page - usually 1 :)
        __last_page
            The number of the last page
        __ previous_page
            The number of the previous page. If this is the first page it returns None.
        __next_page
            The number of the next page. If this is the first page it returns None.
        __page_count
            The number of pages
        __items
            The sequence/iterator of items on the current page
        __current_page
            The page number of current page
        __handler
            The handler of the request which need to paging
        __separator
            The separator of between each page number
        __curpage_attr (optional)
            A dictionary of attributes that get added to the current page number in the pager (which
            is obviously not a link). If this dictionary is not empty then the elements will be
            wrapped in a SPAN tag with the given attributes.

            Example: { 'style':'border: 3px solid blue' }
            Example: { 'class':'pager_curpage' }
        __dotdot_attr (optional)
            A dictionary of attributes that get added to the '..' string in the pager (which is
            obviously not a link). If this dictionary is not empty then the elements will be wrapped
            in a SPAN tag with the given attributes.

            Example: { 'style':'color: #808080' }
            Example: { 'class':'pager_dotdot' }
    """

    def __init__(self, url, document, current_page=1, items_per_page=10, sort=None, pipeline_stages=None,
                 left_pipeline_stages=None, use_pipeline=True, ajax=False, **kwargs):
        if not isinstance(url, str):
            raise ValueError('Parameter url must be type of str or unicode')
        if url.find('$page') == -1:
            raise ValueError('Parameter url must be containing a "$page" placeholder')

        self.__url = url
        self.__document = document
        self.__stages = pipeline_stages
        self.__left_stages = left_pipeline_stages
        self.__use_pipeline = use_pipeline
        self.__items_per_page = items_per_page
        self.__first_page = 1
        self.__current_page = current_page
        self.__query_params = kwargs
        self.__previous_page = 1
        self.__sort = sort
        self.__item_count = 0
        self.__page_count = 1
        self.__next_page = 1
        self.__last_page = 1
        self.__items = []
        self.__first_item = 1
        self.__last_item = 1
        self.__is_ajax = ajax

        self.__separator = ' '
        self.__curpage_attr = None
        self.__dotdot_attr = None
        self.__link_attr = None

        self.__other_pages = None

    async def init_fields(self):
        self.__previous_page = self._get_previous_page()
        self.__sort = self._get_sort_condition(self.__sort)
        self.__item_count = await self._get_item_count()
        self.__page_count = self._get_page_count()
        self.__current_page = self.__page_count if not self.__current_page == 1 \
                                                   and self.__current_page > self.__page_count else self.__current_page
        self.__next_page = self._get_next_page()
        self.__last_page = self._get_last_page()
        self.__items = await self._get_items()
        self.__first_item = (self.__current_page - 1) * self.__items_per_page + 1
        self.__last_item = min(self.__first_item + self.__items_per_page - 1, self.__item_count)

    def _get_sort_condition(self, sort_by):
        if sort_by:
            if isinstance(sort_by, str):
                if sort_by.startswith('-'):
                    return [(sort_by[1:], DESC)]
                else:
                    return [(sort_by, ASC)]
            elif isinstance(sort_by, list):
                sorts = []
                for sort in sort_by:
                    if sort:
                        if sort.startswith('-'):
                            sorts.append((sort[1:], DESC))
                        else:
                            sorts.append((sort, ASC))
                if sorts:
                    return sorts
        return [('updated_dt', DESC)]

    async def _get_item_count(self):
        if self.__use_pipeline:
            pipelines = []
            if self.__query_params:
                pipelines.append(MatchStage(self.__query_params))
            if self.__stages:
                pipelines.extend(self.__stages)
            pipelines.append(CountStage())

            count_list = await self.__document.aggregate(pipelines).to_list(1)
            if count_list:
                return count_list[0].count
        else:
            return await self.__document.count_documents(self.__query_params)
        return 0

    def _get_page_count(self):
        if self.__item_count % self.__items_per_page == 0:
            return int(self.__item_count / self.__items_per_page)
        return int(self.__item_count / self.__items_per_page) + 1

    async def _get_items(self):
        index_s = (self.__current_page - 1) * self.__items_per_page

        if self.__use_pipeline:
            pipelines = []
            if self.__query_params:
                pipelines.append(MatchStage(self.__query_params))
            if self.__stages:
                pipelines.extend(self.__stages)
            if self.__sort:
                sort_stage = SortStage(self.__sort)
                pipelines.append(sort_stage)

            skip_stage = SkipStage(index_s if index_s >= 0 else 0)
            pipelines.append(skip_stage)
            limit_stage = LimitStage(self.__items_per_page)
            pipelines.append(limit_stage)

            if self.__left_stages:
                pipelines.extend(self.__left_stages)

            return await self.__document.aggregate(pipelines).to_list(self.__items_per_page)
        else:
            return await self.__document.find(self.__query_params).skip(index_s).limit(self.__items_per_page).sort(
                self.__sort).to_list(self.__items_per_page)

    def _get_previous_page(self):
        if self.__current_page == 1:
            return 1
        else:
            return self.__current_page - 1

    def _get_next_page(self):
        if self.__current_page == self.__page_count:
            return self.__page_count
        else:
            return self.__current_page + 1

    def _get_last_page(self):
        return self.__page_count

    def _make_html_tag(self, tag, text=None, **params):
        """Create an HTML tag string.

        tag
            The HTML tag to use (e.g. 'a', 'span' or 'div')

        text
            The text to enclose between opening and closing tag. If no text is specified then only
            the opening tag is returned.

        Example::
            make_html_tag('a', text="Hello", href="/another/page") -> <a href="/another/page">Hello</a>

        To use reserved Python keywords like "class" as a parameter prepend it with
        an underscore. Instead of "class='green'" use "_class='green'".

        Warning: Quotes and apostrophes are not escaped."""
        params_string = ''

        # Parameters are passed. Turn the dict into a string like "a=1 b=2 c=3" string.
        for key, value in params.items():
            # Strip off a leading underscore from the attribute's key to allow attributes like '_class'
            # to be used as a CSS class specification instead of the reserved Python keyword 'class'.
            key = key.lstrip('_')

            params_string += ' {0}="{1}"'.format(key, value)

        # Create the tag string
        tag_string = '<{0}{1}>'.format(tag, params_string)

        # Add text and closing tag if required.
        if text:
            tag_string += '{0}</{1}>'.format(text, tag)

        return tag_string

    def _range(self, regexp_match):
        """
        Return range of linked pages (e.g. '1 2 [3] 4 5 6 7 8').

        Arguments:

        regexp_match
            A "re" (regular expressions) match object containing the
            radius of linked pages around the current page in
            regexp_match.group(1) as a string

        This function is supposed to be called as a callable in
        re.sub to replace occurences of ~\d+~ by a sequence of page links.
        """
        radius = int(regexp_match.group(1))

        # Compute the first and last page number within the radius
        # e.g. '1 .. 5 6 [7] 8 9 .. 12'
        # -> leftmost_page  = 5
        # -> rightmost_page = 9
        leftmost_page = max(self.__first_page, (self.__current_page - radius))
        rightmost_page = min(self.__last_page, (self.__current_page + radius))

        nav_items = []

        # Create a link to the first page (unless we are on the first page
        # or there would be no need to insert '..' spacers)
        if self.__current_page != self.__first_page and self.__first_page < leftmost_page:
            nav_items.append(self._pagerlink(self.__first_page, self.__first_page))

        # Insert dots if there are pages between the first page
        # and the currently displayed page range
        if leftmost_page - self.__first_page > 1:
            # Wrap in a SPAN tag if dotdot_attr is set
            text = '..'
            if self.__dotdot_attr:
                text = self._make_html_tag('a', **self.__dotdot_attr) + text + '</a>'
            nav_items.append(text)

        for thispage in range(leftmost_page, rightmost_page + 1):
            # Highlight the current page number and do not use a link
            if thispage == self.__current_page:
                # Wrap in a SPAN tag if curpage_attr is set
                text = str(thispage)
                if self.__curpage_attr:
                    text = self._make_html_tag('a', **self.__curpage_attr) + text + '</a>'
                nav_items.append(text)
            # Otherwise create just a link to that page
            else:
                text = str(thispage)
                nav_items.append(self._pagerlink(thispage, text))

        # Insert dots if there are pages between the displayed
        # page numbers and the end of the page range
        if self.__last_page - rightmost_page > 1:
            # Wrap in a SPAN tag if dotdot_attr is set
            text = '<a href="javascript:;">...</a>'
            if self.__dotdot_attr:
                text = self._make_html_tag('a', **self.__dotdot_attr) + text + '</a>'
            nav_items.append(text)

        # Create a link to the very last page (unless we are on the last
        # page or there would be no need to insert '..' spacers)
        if self.__current_page != self.__last_page and rightmost_page < self.__last_page:
            nav_items.append(self._pagerlink(self.__last_page, self.__last_page))

        return self.__separator.join(nav_items)

    def _pagerlink(self, page_number, text):
        """
        Create an A-HREF tag that points to another page.

        Parameters:

        page
            Number of the page that the link points to

        text
            Text to be printed in the A-HREF tag
        """
        target_url = self.__url.replace('$page', str(page_number))
        if self.__is_ajax:
            a_tag = self._make_html_tag('a', text=text, href='javascript:void(0);',
                                        onclick="do_jump_2_link(event, $(this), '{0}')".format(target_url),
                                        **self.__link_attr)
        else:
            a_tag = self._make_html_tag('a', text=text, href=target_url, **self.__link_attr)
        return a_tag

    async def pager(self, format='~2~', show_if_single_page=True, separator=' ', symbol_first='&lt;&lt;',
                    symbol_last='&gt;&gt;', symbol_previous='&lt;', symbol_next='&gt;', link_attr=dict(),
                    curpage_attr={'class': 'active'}, dotdot_attr=dict()):
        """
        Return string with links to other pages (e.g. '1 .. 5 6 7 [8] 9 10 11 .. 50').

        format:
            Format string that defines how the pager is rendered. The string
            can contain the following $-tokens that are substituted by the
            string.Template module:

            - $first_page: number of first reachable page
            - $last_page: number of last reachable page
            - $page: number of currently selected page
            - $page_count: number of reachable pages
            - $items_per_page: maximal number of items per page
            - $item_count: total number of items
            - $link_first: link to first page (unless this is first page)
            - $link_last: link to last page (unless this is last page)
            - $link_previous: link to previous page (unless this is first page)
            - $link_next: link to next page (unless this is last page)

            To render a range of pages the token '~3~' can be used. The
            number sets the radius of pages around the current page.
            Example for a range with radius 3:

            '1 .. 5 6 7 [8] 9 10 11 .. 50'

            Default: '~2~'

        url
            The URL that page links will point to. Make sure it contains the string
            $page which will be replaced by the actual page number.

        symbol_first
            String to be displayed as the text for the $link_first link above.

            Default: '&lt;&lt;' (<<)

        symbol_last
            String to be displayed as the text for the $link_last link above.

            Default: '&gt;&gt;' (>>)

        symbol_previous
            String to be displayed as the text for the $link_previous link above.

            Default: '&lt;' (<)

        symbol_next
            String to be displayed as the text for the $link_next link above.

            Default: '&gt;' (>)

        separator:
            String that is used to separate page links/numbers in the above range of pages.

            Default: ' '

        show_if_single_page:
            if True the navigator will be shown even if there is only one page.

            Default: False

        link_attr (optional)
            A dictionary of attributes that get added to A-HREF links pointing to other pages. Can
            be used to define a CSS style or class to customize the look of links.

            Example: { 'style':'border: 1px solid green' }
            Example: { 'class':'pager_link' }

        curpage_attr (optional)
            A dictionary of attributes that get added to the current page number in the pager (which
            is obviously not a link). If this dictionary is not empty then the elements will be
            wrapped in a SPAN tag with the given attributes.

            Example: { 'style':'border: 3px solid blue' }
            Example: { 'class':'pager_curpage' }

        dotdot_attr (optional)
            A dictionary of attributes that get added to the '..' string in the pager (which is
            obviously not a link). If this dictionary is not empty then the elements will be wrapped
            in a SPAN tag with the given attributes.

            Example: { 'style':'color: #808080' }
            Example: { 'class':'pager_dotdot' }

        Additional keyword arguments are used as arguments in the links.
        """
        # 初始化分页参数
        await self.init_fields()

        self.__curpage_attr = curpage_attr
        self.__dotdot_attr = dotdot_attr
        self.__link_attr = link_attr
        self.__separator = separator

        # Don't show navigator if there is no more than one page
        if self.__page_count == 1 and not show_if_single_page:
            self.__other_pages = ''

        # Replace ~...~ in token format by range of pages
        result = re.sub(r'~(\d+)~', self._range, format)

        # Interpolate '$' variables
        result = Template(result).safe_substitute({
            'first_page': self.__first_page,
            'last_page': self.__last_page,
            'page': self.__current_page,
            'page_count': self.__page_count,
            'items_per_page': self.__items_per_page,
            'first_item': self.__first_item,
            'last_item': self.__last_item,
            'item_count': self.__item_count,
            'link_first': self.__current_page > self.__first_page and self._pagerlink(self.__first_page,
                                                                                      symbol_first) or '',
            'link_last': self.__current_page < self.__last_page and self._pagerlink(self.__last_page,
                                                                                    symbol_last) or '',
            'link_previous': self.__previous_page and self._pagerlink(self.__previous_page, symbol_previous) or '',
            'link_next': self.__next_page and self._pagerlink(self.__next_page, symbol_next) or ''
        })
        self.__other_pages = result

    @property
    def per_page_quantity(self):
        return self.__items_per_page

    @property
    def total_pages(self):
        return self.__page_count

    @property
    def current_page_num(self):
        return self.__current_page

    @property
    def previous_page_num(self):
        return self.__previous_page

    @property
    def next_page_num(self):
        return self.__next_page

    @property
    def page_items(self):
        return self.__items

    @property
    def total_items(self):
        return self.__item_count

    @property
    def other_pages_html(self):
        return self.__other_pages
