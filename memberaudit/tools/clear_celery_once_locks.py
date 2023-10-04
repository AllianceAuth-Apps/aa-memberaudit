"""Tool for clearing celery locks."""

import argparse

from redis import Redis


def main():
    """Clear all celery once locks (if any exist)."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--redis-url", default="redis://127.0.0.1:6379/1", help="REDIS URL"
    )
    parser.add_argument("--app-label", default="memberaudit", help="Django app label")
    args = parser.parse_args()

    r = Redis.from_url(args.redis_url)
    if keys := r.keys(f":?:qo_{args.app_label}.*"):
        deleted_count = r.delete(*keys)
    else:
        deleted_count = 0
    print(f"Removed {deleted_count} stuck celery once keys")


if __name__ == "__main__":
    main()
