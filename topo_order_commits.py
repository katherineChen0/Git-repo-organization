#!/usr/bin/env python3

import os
import sys
import zlib
from collections import deque

class CommitNode:
    def __init__(self, commit_hash):
        """
        :type commit_hash: str
        """
        self.commit_hash = commit_hash
        self.parents = set()
        self.children = set()

def get_git_directory():
    """
    Find the .git directory by traversing up from the current directory.
    Returns the path to the .git directory or exits with error if not found.
    
    :rtype: str
    """
    curr_path = os.getcwd()
    while curr_path != '/':
        git_path = os.path.join(curr_path, '.git')
        if os.path.isdir(git_path):
            return git_path
        curr_path = os.path.dirname(curr_path)
    
    sys.stderr.write('Not inside a Git repository\n')
    sys.exit(1)

def get_branches(git_dir):
    """
    Get all local branch names and their corresponding commit hashes.
    
    :type git_dir: str
    :rtype: list[tuple[str, str]]
    """
    heads_dir = os.path.join(git_dir, 'refs', 'heads')
    branches = []
    
    # Walk through the refs/heads directory
    for root, _, files in os.walk(heads_dir):
        for file in files:
            branch_path = os.path.join(root, file)
            # Read the commit hash from the branch file
            with open(branch_path, 'r') as f:
                commit_hash = f.read().strip()
            
            # Get the branch name relative to heads_dir
            rel_path = os.path.relpath(branch_path, heads_dir)
            branch_name = rel_path.replace(os.sep, '/')
            branches.append((branch_name, commit_hash))
    
    return branches

def decompress_git_object(git_dir, commit_hash):
    """
    Decompress and read a Git object.
    
    :type git_dir: str
    :type commit_hash: str
    :rtype: list[str]
    """
    obj_path = os.path.join(git_dir, 'objects', commit_hash[:2], commit_hash[2:])
    if not os.path.exists(obj_path):
        return []
    
    with open(obj_path, 'rb') as f:
        compressed = f.read()
    
    decompressed = zlib.decompress(compressed).decode()
    return decompressed.split('\n')

def build_commit_graph(git_dir, branches_list):
    """
    Build the commit graph using the branch heads as starting points.
    
    :type git_dir: str
    :type branches_list: list[tuple[str, str]]
    :rtype: dict[str, CommitNode]
    """
    graph = {}
    
    # Using iterative approach to avoid recursion depth issues
    stack = []
    for _, commit_hash in branches_list:
        stack.append(commit_hash)
    
    visited = set()
    
    while stack:
        commit_hash = stack.pop()
        
        if commit_hash in visited:
            continue
            
        visited.add(commit_hash)
        
        # Create node if it doesn't exist
        if commit_hash not in graph:
            graph[commit_hash] = CommitNode(commit_hash)
        
        # Decompress and read commit object
        lines = decompress_git_object(git_dir, commit_hash)
        
        # Extract parent hashes
        for line in lines:
            if line.startswith('parent'):
                parent_hash = line.split()[1]
                
                # Create parent node if it doesn't exist
                if parent_hash not in graph:
                    graph[parent_hash] = CommitNode(parent_hash)
                
                # Add to parent-child relationships
                graph[commit_hash].parents.add(parent_hash)
                graph[parent_hash].children.add(commit_hash)
                
                # Add parent to stack for processing
                stack.append(parent_hash)
            
            elif line == '':
                break  # End of header section
    
    return graph

def topo_sort(commit_nodes):
    """
    Perform topological sort on the commit graph.
    
    :type commit_nodes: dict[str, CommitNode]
    :rtype: list[str]
    """
    in_degree = {}
    for hash_, node in commit_nodes.items():
        in_degree[hash_] = len(node.parents)
    
    # Start with nodes having no parents (root commits)
    queue = deque([hash_ for hash_, degree in in_degree.items() if degree == 0])
    queue = deque(sorted(queue))  # Sort for determinism
    
    result = []
    
    while queue:
        current = queue.popleft()
        result.append(current)
        
        # Process children
        for child in sorted(commit_nodes[current].children):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
                queue = deque(sorted(queue))  # Keep deterministic ordering
    
    # Reverse the result to get commits from least to greatest (descendants first)
    return list(reversed(result))

def print_topo_ordered_commits(commit_nodes, topo_ordered_commits, head_to_branches):
    """
    Print the topologically ordered commits with sticky start/end lines.
    
    :type commit_nodes: dict[str, CommitNode]
    :type topo_ordered_commits: list[str]
    :type head_to_branches: dict[str, list[str]]
    """
    prev = None
    
    for i, commit_hash in enumerate(topo_ordered_commits):
        # If not the first commit and current commit is not a child of previous commit
        if prev is not None and prev not in commit_nodes[commit_hash].children:
            # Print sticky end
            if commit_nodes[prev].parents:
                print(f"{' '.join(sorted(commit_nodes[prev].parents))}=")
            else:
                print("=")
            
            print()  # Empty line
            
            # Print sticky start
            children = sorted(commit_nodes[commit_hash].children)
            print(f"={''.join([' ' + c for c in children]) if children else ''}")
        
        # Print commit hash and branch names if any
        branches = head_to_branches.get(commit_hash, [])
        if branches:
            print(f"{commit_hash} {' '.join(sorted(branches))}")
        else:
            print(commit_hash)
        
        prev = commit_hash

def topo_order_commits():
    """
    Main function to orchestrate the topological ordering of commits.
    """
    git_dir = get_git_directory()
    branches = get_branches(git_dir)
    
    # Map commit hashes to branch names
    head_to_branches = {}
    for branch_name, commit_hash in branches:
        if commit_hash not in head_to_branches:
            head_to_branches[commit_hash] = []
        head_to_branches[commit_hash].append(branch_name)
    
    # Build the commit graph
    commit_nodes = build_commit_graph(git_dir, branches)
    
    # Get topological ordering
    topo_ordered_commits = topo_sort(commit_nodes)
    
    # Print the result
    print_topo_ordered_commits(commit_nodes, topo_ordered_commits, head_to_branches)

if __name__ == '__main__':
    topo_order_commits()
