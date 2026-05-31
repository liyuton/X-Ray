# Git 操作介绍

本文档假设 Git 已经配置完成，例如已经设置好用户名、邮箱以及远程仓库权限。

## Git 简介

Git 是一个版本控制工具，用来记录文件的修改历史。它可以帮助我们追踪代码或文档在什么时候、由谁、因为什么原因发生了变化。

在没有 Git 的情况下，如果想保存不同版本，常见做法可能是复制多个文件夹，例如 `project_v1`、`project_v2`、`project_final`。这种方式很难看清每个版本具体改了什么，也不方便多人同时修改。Git 的作用就是用更清晰、可追踪的方式管理这些变化。

Git 会把项目中的文件变化保存成一次次提交，也就是 commit。每次 commit 都像是项目在某个时间点的快照，里面包含本次修改的文件、修改内容和提交说明。以后如果需要查看历史、比较差异、恢复旧版本，都可以通过这些提交记录完成。

Git 通常分为本地仓库和远程仓库：

- 本地仓库：保存在自己电脑上的 Git 仓库，日常的 `add`、`commit` 都是在本地完成。
- 远程仓库：保存在 GitHub、GitLab 等平台上的仓库，用来备份代码、多人共享和协作开发。

使用 Git 的主要作用包括：

- 保存不同阶段的项目版本，方便以后查看或回退。
- 记录每次修改的具体内容，方便定位问题。
- 支持多人协作，减少互相覆盖代码的风险。
- 配合 GitHub、GitLab 等远程仓库，可以在不同电脑之间同步项目。
- 通过分支管理不同任务，例如新功能开发、问题修复和实验性修改。

## 第一部分：基础操作

基础流程可以记为：

```bash
git add
git commit
git push
```

这三个命令分别对应：选择要提交的文件、生成一次本地提交、推送到远程仓库。

### 1. 命令行操作

#### 查看当前状态

```bash
git status
```

常用来确认哪些文件被修改了、哪些文件已经进入暂存区、当前分支是否领先或落后远程分支。

#### 添加文件到暂存区

添加单个文件：

```bash
git add AGENTS.md
```

添加当前目录下所有改动：

```bash
git add .
```

`git add` 不会生成提交，只是告诉 Git：这些改动准备放进下一次提交。

#### 提交改动

```bash
git commit -m "add agents.md file"
```

`-m` 后面是提交信息。提交信息建议简短、明确，说明这次改动做了什么。

例如：

```bash
git commit -m "add git operation guide"
```

#### 推送到远程仓库

```bash
git push
```

如果是第一次推送当前分支，可能需要指定远程分支：

```bash
git push -u origin main
```

其中 `origin` 是远程仓库名，`main` 是分支名。项目如果使用 `master` 或其他分支名，需要替换成对应名称。

### 2. VS Code 操作

#### 查看改动

打开 VS Code 左侧的 Source Control 图标，通常是分支形状的图标。

在这里可以看到当前修改过的文件。点击某个文件，可以查看本次修改前后的差异。

#### 暂存改动

在 Source Control 面板中：

- 点击单个文件旁边的 `+`，暂存这个文件。
- 点击 Changes 区域旁边的 `+`，暂存全部改动。

暂存后的文件会进入 Staged Changes 区域。

#### 提交改动

在 Source Control 面板顶部的输入框中填写提交信息，例如：

```text
add git operation guide
```

然后点击 Commit 按钮，或者使用快捷操作提交。

#### 推送到远程仓库

提交完成后，点击 Sync Changes 或 Push。

如果 VS Code 提示选择远程分支，通常选择当前项目对应的远程仓库和分支即可。

## 第二部分：进阶操作

进阶操作主要用于处理分支协作、同步远程代码、撤销错误改动和查看历史。

### 1. 命令行操作

#### 查看提交历史

```bash
git log --oneline
```

这会用简洁形式显示提交记录，例如：

```text
a1b2c3d add git operation guide
```

#### 查看分支

```bash
git branch
```

查看本地和远程分支：

```bash
git branch -a
```

#### 创建并切换分支

```bash
git switch -c feature/git-guide
```

这会创建一个名为 `feature/git-guide` 的新分支，并切换到该分支。

#### 切换已有分支

```bash
git switch main
```

如果项目主分支叫 `master`，则使用：

```bash
git switch master
```

#### 拉取远程更新

```bash
git pull
```

`git pull` 会从远程仓库拉取最新代码，并合并到当前分支。

在多人协作时，建议在开始修改前先执行：

```bash
git pull
```

#### 查看具体改动

查看尚未暂存的改动：

```bash
git diff
```

查看已经暂存、准备提交的改动：

```bash
git diff --staged
```

#### 撤销未暂存的本地修改

撤销某个文件的修改：

```bash
git restore AGENTS.md
```

注意：这会丢弃该文件尚未暂存的本地改动。

#### 取消暂存

如果已经执行了 `git add`，但还不想提交某个文件：

```bash
git restore --staged AGENTS.md
```

这只会把文件从暂存区移出，不会删除文件内容。

#### 修改最近一次提交信息

如果刚提交完，发现提交信息写错了：

```bash
git commit --amend -m "add repository git guide"
```

如果这次提交已经推送到远程仓库，修改提交历史可能影响协作者，操作前需要谨慎。

### 2. VS Code 操作

#### 查看历史记录

VS Code 自带的 Git 面板可以查看当前改动。若安装 Git Graph、GitLens 等扩展，可以更直观地查看分支和提交历史。

#### 创建和切换分支

点击 VS Code 左下角的当前分支名，可以：

- 切换到已有分支。
- 从当前分支创建新分支。
- 从远程分支创建本地分支。

#### 拉取和同步

在 Source Control 面板中可以点击：

- Pull：拉取远程更新。
- Push：推送本地提交。
- Sync Changes：同步本地和远程改动。

多人协作时，修改前先 Pull，提交后再 Push，可以减少冲突。

#### 解决冲突

当 `git pull` 或合并分支时出现冲突，VS Code 会在冲突文件中显示选择按钮，例如：

- Accept Current Change：保留当前分支的内容。
- Accept Incoming Change：保留传入分支的内容。
- Accept Both Changes：保留两边内容。
- Compare Changes：对比冲突内容。

解决冲突后，需要重新暂存并提交：

```bash
git add .
git commit -m "resolve merge conflicts"
```

#### 丢弃本地改动

在 Source Control 面板中，文件旁边通常有 Discard Changes 操作。

使用前要确认这些改动确实不需要了，因为丢弃后很难恢复。

## 常用推荐流程

### 单人修改

```bash
git status
git add .
git commit -m "describe your change"
git push
```

### 多人协作

```bash
git pull
git status
git add .
git commit -m "describe your change"
git push
```

### 新功能开发

```bash
git pull
git switch -c feature/new-work
git add .
git commit -m "add new work"
git push -u origin feature/new-work
```

## 注意事项

- 提交前先运行 `git status`，确认提交内容是否正确。
- 提交信息要说明本次改动，不建议只写 `update` 或 `fix`。
- 不要把临时文件、大型生成文件、密码、密钥提交到仓库。
- 不确定一个命令是否会丢失改动时，先不要执行，先查看 `git status` 和 `git diff`。
