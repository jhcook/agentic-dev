
import os

def get_current_story_file():
    # This function assumes the story file is in a specific location
    # and follows a specific naming convention.
    cache_dir = "../cache/stories/INFRA/"
    story_files = [f for f in os.listdir(cache_dir) if f.startswith("INFRA-") and f.endswith(".md")]
    if story_files:
        return os.path.join(cache_dir, story_files[0])
    else:
        return None


def read_current_story():
    story_file = get_current_story_file()
    if story_file:
        with open(story_file, "r") as f:
            return f.read()
    else:
        return "No story file found."


def main():
    print(read_current_story())

if __name__ == "__main__":
    main()
