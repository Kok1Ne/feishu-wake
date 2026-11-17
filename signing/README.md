# 固定签名

应用包名固定为 `dev.feishuwake`。RSA 3072 位密钥于 2026-11-17 在 GitHub 标准云端运行器生成。

固定证书 SHA-256：`323c450b86e5e0439bd0928e7ad574daa08fe2e5b66c13ea68aa9fe2cba96a45`。

密钥的 AES-256-GCM 加密备份仅保存于 `FEISHU_SIGNING_VAULT` 仓库加密 Secret，保护密码保存于独立的 `FEISHU_SIGNING_PASSWORD` Secret。公开源码不包含密钥备份或密码。

后续版本只能使用同一密钥；`vault.mjs restore` 会同时核对私密备份中的证书和本目录固定指纹。明文密钥及 signing.properties 只在临时云端运行器存在，不上传至构建产物。初始化功能已经移除，避免误生成新密钥。

该签名属于 Feishu Wake，与飞书官方客户端的签名不同。
