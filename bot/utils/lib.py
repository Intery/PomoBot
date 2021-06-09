import datetime
import pytz


def prop_tabulate(prop_list, value_list):
    """
    Turns a list of properties and corresponding list of values into
    a pretty string with one `prop: value` pair each line,
    padded so that the colons in each line are lined up.
    Handles empty props by using an extra couple of spaces instead of a `:`.

    Parameters
    ----------
    prop_list: List(str)
        List of short names to put on the right side of the list.
        Empty props are considered to be "newlines" for the corresponding value.
    value_list: List(str)
        List of values corresponding to the properties above.

    Returns: str
    """
    max_len = max(len(prop) for prop in prop_list)
    return "\n".join(["`{}{}{}`\t{}".format("​ " * (max_len - len(prop)),
                                            prop,
                                            ":" if len(prop) > 1 else "​ " * 2,
                                            value_list[i]) for i, prop in enumerate(prop_list)])


def paginate_list(item_list, block_length=20, style="markdown", title=None):
    """
    Create pretty codeblock pages from a list of strings.

    Parameters
    ----------
    item_list: List(str)
        List of strings to paginate.
    block_length: int
        Maximum number of strings per page.
    style: str
        Codeblock style to use.
        Title formatting assumes the `markdown` style, and numbered lists work well with this.
        However, `markdown` sometimes messes up formatting in the list.
    title: str
        Optional title to add to the top of each page.

    Returns: List[str]
        List of pages, each formatted into a codeblock,
        and containing at most `block_length` of the provided strings.
    """
    lines = ["{0:<5}{1:<5}".format("{}. ".format(i + 1), str(line)) for i, line in enumerate(item_list)]
    page_blocks = [lines[i:i + block_length] for i in range(0, len(lines), block_length)]
    pages = []
    for i, block in enumerate(page_blocks):
        pagenum = "Page {}/{}".format(i + 1, len(page_blocks))
        if title:
            header = "{} ({})".format(title, pagenum) if len(page_blocks) > 1 else title
        else:
            header = pagenum
        header_line = "=" * len(header)
        full_header = "{}\n{}\n".format(header, header_line) if len(page_blocks) > 1 or title else ""
        pages.append("```{}\n{}{}```".format(style, full_header, "\n".join(block)))
    return pages


def timestamp_utcnow():
    """
    Return the current integer UTC timestamp.
    """
    return int(datetime.datetime.now(tz=pytz.utc).timestamp())


class DotDict(dict):
    """
    Dict-type allowing dot access to keys.
    """
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
