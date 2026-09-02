# doc_tmplate

把一篇飞书文档一键生成基于 Sphinx（Read the Docs 主题）的静态文档站，并可通过 GitHub Pages 部署。这是一个模板项目：复制到任意仓库后，传入不同的飞书文档 URL 即可生成各自的文档站。

## 前置条件

- Python 3.10+
- `lark-cli`（已登录：`lark-cli auth login`），用于拉取飞书文档

## 使用方式

首次使用先安装依赖（创建 `.venv`）：

```bash
make install
```

一条命令完成「拉取飞书文档 → 切分章节 → 图片本地化 → 构建 HTML」：

```bash
make docs DOC="https://xxx.feishu.cn/docx/XXXX"
```

生成的站点在 `docs/_build/html/`，本地预览：

```bash
make serve   # http://127.0.0.1:8000/
```

其他入口：

```bash
make sync DOC=<url>        # 只同步章节源码（docs/source/）
make html                  # 只构建
make sync FROM=local.md    # 离线/调试：从本地 Markdown 文件生成（不走 lark-cli）
```

也可以用环境变量代替参数：`LARK_DOC_URL=<url> make docs DOC="$LARK_DOC_URL"`。

## 部署到 GitHub Pages

1. `make docs DOC=<url>` 后提交生成的 `docs/source/`（章节 Markdown 和本地图片都在里面，CI 不需要飞书权限）。
2. 仓库 Settings → Pages → Source 选择 **GitHub Actions**。
3. push 到 `main`（或 `master`），`.github/workflows/docs.yml` 会自动构建部署。
4. 站点地址：`https://<user>.github.io/<repo>/`（Sphinx 使用相对路径，无需配置 base path）。

## 工作原理

```
飞书文档 --(lark-cli +fetch， Markdown 格式)--> doc_scripts/sync_lark_doc.py
  ├── 按一级标题切分为 docs/source/chapters/NN-<slug>.md
  ├── 远程图片下载到 docs/source/assets/images/<slug>/，并改写引用
  ├── 生成 docs/source/index.md（标题 + 前言 + toctree）
  └── 写入 docs/project.json（站点标题、来源、同步时间）
sphinx-build（myst-parser + sphinx_rtd_theme）--> docs/_build/html/
```

- 文档的 Markdown 由 `myst-parser` 解析，启用了 `dollarmath` / `amsmath`（飞书公式可渲染）、`colon_fence` 等扩展。
- `docs/source/conf.py` 一般不碰；站点标题等元数据由 sync 写入 `docs/project.json`，`conf.py` 自动读取。需要自定义主题选项时直接改 `conf.py`。
- 重新 sync 只会重建 `docs/source/chapters/`、`docs/source/assets/images/`、`index.md` 和 `docs/project.json`，不影响其它文件。

## 复制到其他项目

整个目录即模板，复制时需要的一切都在仓库内：

```
Makefile  requirements.txt  doc_scripts/  docs/  .github/workflows/docs.yml
```

复制后按上面的流程 `make install && make docs DOC=<url>` 即可；不同项目只需传不同的 `DOC`。

## 注意事项

- 图片下载的是飞书导出的临时签名 URL，sync 时会本地化为仓库内文件，请及时提交。
- 章节按文档中的一级标题（H1）切分；文件名 slug 从标题提取，纯中文标题会退化为 `NN-chapter`。
- `make sync` 依赖本机 `lark-cli` 的登录态；CI 只负责构建，不会访问飞书。
