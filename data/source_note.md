# 数据来源说明

默认数据集来自 UCI Machine Learning Repository 的 Online Retail 数据集：

https://archive.ics.uci.edu/dataset/352/online+retail

转换方式：

- 下载原始压缩包 `online+retail.zip`，其中包含 `Online Retail.xlsx`。
- 从原始 541,909 行交易中筛选 France 正向订单。
- 删除取消订单、非正数量、邮费、人工费用、折扣等非商品记录。
- 按 `InvoiceNo` 聚合商品描述，转换为购物篮格式。
- 为保证课程网站运行速度，保留高频真实商品并输出 160 条交易到 `transactions.csv`。

`transactions.csv` 字段：

- `transaction_id`：由 UCI 发票号派生的交易编号。
- `items`：同一交易中的商品描述，使用英文逗号分隔。
