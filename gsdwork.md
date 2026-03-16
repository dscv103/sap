name: GSD from Issue Comment

on:
  issue_comment:
    types: [created]

jobs:
  gsd:
    if: |
      !github.event.issue.pull_request &&
      contains(github.event.comment.body, ‘@gsd’)
    runs-on: self-hosted

    permissions:
      contents: write
      issues: write

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: ‘20’

      - name: Install Claude Code + GSD
        run: |
          npm install -g @anthropic-ai/claude-code
          npx get-shit-done-cc —claude —local

      - name: Configure git
        run: |
          git config user.name “gsd-bot”
          git config user.email “gsd@standard-syntax.dev”

      - name: Build task from issue + comment
        id: task
        run: |
          # Use the comment text after @gsd if provided, else fall back to issue body
          COMMENT=“${{ github.event.comment.body }}”
          OVERRIDE=$(echo “$COMMENT” | sed ‘s/@gsd//‘ | xargs)

          if [ -n “$OVERRIDE” ]; then
            TASK=“$OVERRIDE (context: ${{ github.event.issue.title }})”
          else
            TASK=“${{ github.event.issue.title }}: ${{ github.event.issue.body }}”
          fi

          echo “task=$TASK” >> $GITHUB_OUTPUT

      - name: Run GSD
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          claude -p —dangerously-skip-permissions “/gsd:do ${{ steps.task.outputs.task }} —full”

      - name: Push + comment back
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git push origin HEAD
          gh issue comment ${{ github.event.issue.number }} \
            —body “✅ GSD finished. Check commits on this branch.”
