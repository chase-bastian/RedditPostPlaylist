import praw

def get_top_lvl_comments(submission):
    return [comment for comment in submission.comments.list() if (isinstance(comment, praw.models.Comment) and comment.is_root)]