from sqlmodel import Session, col, select

from app.models import Post, PostStatus, Profile


class PostRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, post: Post) -> Post:
        self.session.add(post)
        self.session.commit()
        self.session.refresh(post)
        return post

    def create_many(self, posts: list[Post]) -> list[Post]:
        for post in posts:
            self.session.add(post)
        self.session.commit()
        for post in posts:
            self.session.refresh(post)
        return posts

    def get_by_id(self, post_id: int) -> Post | None:
        return self.session.get(Post, post_id)

    def list_by_status(self, status: PostStatus) -> list[Post]:
        statement = select(Post).where(Post.status == status).order_by(col(Post.created_at).desc())
        return list(self.session.exec(statement).all())

    def update_status(self, post: Post, status: PostStatus) -> Post:
        post.status = status
        self.session.add(post)
        self.session.commit()
        self.session.refresh(post)
        return post

    def delete(self, post: Post) -> None:
        self.session.delete(post)
        self.session.commit()


class ProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self) -> Profile | None:
        return self.session.exec(select(Profile)).first()

    def save(self, profile: Profile) -> Profile:
        existing = self.get()
        if existing:
            existing.name = profile.name
            existing.niche = profile.niche
            existing.tone = profile.tone
            existing.platform = profile.platform
            existing.audience_description = profile.audience_description
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile
