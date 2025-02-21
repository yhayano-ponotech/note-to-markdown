import os
import yaml
import argparse

def search_articles_by_title_word(posts_dir, search_word):
    """
    Search for article files containing specific word in their titles
    
    Args:
        posts_dir (str): Directory path containing markdown files
        search_word (str): Word to search for in titles
        
    Returns:
        list: List of matching filenames
    """
    matching_files = []
    
    for filename in os.listdir(posts_dir):
        if not filename.endswith('.md'):
            continue
            
        file_path = os.path.join(posts_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract YAML frontmatter between --- markers
            if content.startswith('---'):
                _, frontmatter, _ = content.split('---', 2)
                metadata = yaml.safe_load(frontmatter)
                
                if 'title' in metadata:
                    title = metadata['title']
                    if search_word.lower() in title.lower():
                        matching_files.append(filename)
                        
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
            
    matching_files.sort()
    return matching_files

def main():
    parser = argparse.ArgumentParser(description='Search for articles by title word')
    parser.add_argument('word', help='Word to search for in article titles')
    parser.add_argument('--dir', default='posts', help='Directory containing markdown files (default: posts)')
    
    args = parser.parse_args()
    
    # Get absolute path of posts directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    posts_dir = os.path.join(script_dir, args.dir)
    
    if not os.path.exists(posts_dir):
        print(f"Error: Directory '{args.dir}' not found")
        return
        
    matching_files = search_articles_by_title_word(posts_dir, args.word)
    
    if matching_files:
        print(f"\nFound {len(matching_files)} matching article(s):")
        for filename in matching_files:
            print(f"- {filename}")
    else:
        print(f"\nNo articles found containing '{args.word}' in title")

if __name__ == '__main__':
    main()
