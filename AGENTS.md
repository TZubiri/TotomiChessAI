1. after each user request and agent response, git add and git commit all changes. If there's any files that are not source code, add them to .gitignore and commit that too.
2. always try to work with builtins. If you must, install what you can with apt. If you really really must install something with pip, ask the user. Never install something that isn't in an approved package manager.
3. try to add tests whenever you add features. And whenever you fix a bug.
