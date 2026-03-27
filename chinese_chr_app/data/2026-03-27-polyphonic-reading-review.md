# 2026-03-27 Polyphonic reading coverage review

This note records the manual review pass for uncovered polyphonic readings in `extracted_characters_hwxnet.json`, using the stricter coverage definition:

- A reading is `covered` only if it has at least one sample word/example from any of:
  - `基本字义解释 -> 释义 -> 例词`
  - `常用词组按拼音 -> Phrases`
  - `WordsByPinyin -> Phrases`

## Summary

- Review CLI: `chinese_chr_app/chinese_chr_app/backend/scripts/characters/review_uncovered_polyphonic_readings.py`
- Decisions artifact: `chinese_chr_app/data/hwxnet_polyphonic_uncovered_reading_decisions.json`
- In-place apply target: `chinese_chr_app/data/extracted_characters_hwxnet.json`
- Backup created before overwrite:
  - `chinese_chr_app/data/backups/extracted_characters_hwxnet.20260327-polyphonic-reading-review-backup.json`

Decision totals:

- Uncovered reading candidates reviewed: `529`
- `missing_entry` readings: `350`
- `has_entry_no_examples` readings: `179`
- Removed readings: `506`
- Added sample words into `常用词组按拼音`: `23`

## Added sample words

- `匙 shi -> 钥匙`
- `单 chán -> 单于`
- `卜 bo -> 萝卜`
- `叉 chà -> 分叉`
- `呛 qiàng -> 油烟很呛`
- `嗯 ǹg -> 嗯声`
- `嘛 má -> 干嘛`
- `大 dài -> 大夫`
- `岗 gāng -> 黄冈`
- `徊 huái -> 徘徊`
- `桔 jú -> 桔色`
- `槛 kǎn -> 门槛`
- `氓 máng -> 流氓`
- `汗 hán -> 可汗`
- `瘩 da -> 疙瘩`
- `皖 wǎn -> 皖（安徽）`
- `苔 tāi -> 舌苔`
- `落 là -> 落在后面`
- `薇 wēi -> 紫薇`
- `蟆 ma -> 蛤蟆`
- `裳 shang -> 衣裳`
- `贾 jiǎ -> 贾宝玉`
- `逮 dǎi -> 逮住`

## Removed readings

The following `character + reading` pairs were removed from the curated HWXNet JSON. For entries in the `has_entry_no_examples` bucket, this removal also deletes the matching `基本字义解释` sense, not just the top-level `拼音` reading.

```text
万 mò、上 shǎng、不 bú、不 fǒu、与 yú、丧 sang、个 gě、么 ma、么 yāo、乌 wù、乾 gān、了 liào、些 xie、亡 wú、亲 qin、什 shé、仇 qiú、从 cōng、令 lǐng、任 rén、企 qì、伐 fā、伯 bà、伯 bǎi、佃 tián、体 bèn、何 hè、余 tú、作 zuó、使 shì、侥 jiǎ、侥 yáo、侧 zè、侯 hòu、俄 è、俊 juàn、俊 zùn、信 shēn、俱 jū、傍 bāng、兀 wū、免 wèn、八 bá、六 lù、共 gōng、共 gǒng、其 jī、兹 cí、写 xiè、冯 píng、凸 gǔ、凸 tú、凿 zuò、划 huai、别 biè、刻 kē、削 xuè、剖 pǒ、剖 pǒu、剿 jiǎ、努 náo、勘 kàn、勺 biāo、勺 shuò、化 huā、匹 pī、匹 yǎ、区 ōu、华 huà、华 huā、卓 zhuō、单 shàn、南 nā、危 wéi、卷 quán、厂 hǎn、厂 ān、厕 si、叔 shú、句 gōu、叨 dáo、召 shào、召 zhāo、台 tāi、吁 yū、吃 jí、合 gě、同 tòng、听 yǐn、吱 zī、吹 chuì、呀 ya、呆 ái、告 gù、呐 na、呐 ne、呐 nè、呕 òu、员 yùn、员 yún、呢 nà、呢 nè、呱 guǎ、呱 gū、呱 wā、咀 zuǐ、咄 duò、和 he、和 huo、和 hāi、咐 fu、咱 zá、咳 kài、咳 kǎ、哇 wa、哈 kā、哎 ài、哎 ǎi、哑 yā、哗 yè、哟 yo、哦 wò、哦 wó、哦 é、哩 li、哩 lǐ、哪 nǎi、哮 xiāo、唬 xià、唯 wěi、啊 a、喇 lá、喇 lā、喷 pen、嗯 ňg、嘿 hāi、嘿 mò、嚼 jiào、圈 quǎn、场 chang、均 yùn、坏 pī、坷 kě、堆 zuī、堕 huī、堡 pǔ、堤 tí、塔 da、夏 jiǎ、夕 xì、夭 yǎo、夯 bèn、夹 gā、奄 yān、奈 nǎi、契 qiè、契 xiè、女 rǔ、妨 fāng、妻 qì、姥 mǔ、娶 qù、子 zi、子 zí、宅 zhè、宛 yuān、家 gū、家 jie、寂 jí、射 shí、尺 chě、尿 nì、居 jī、屹 gē、崖 ái、嵌 kàn、嵌 qiān、巍 wéi、巫 wú、帆 fán、并 bīng、广 ān、底 de、度 duò、往 wàng、徊 huí、微 wéi、忘 wáng、怎 zě、怜 líng、思 sāi、怯 què、息 xí、情 qing、惜 xí、惨 càn、慌 huang、慨 kài、慷 kǎng、戌 qu、戏 hū、扒 pā、押 yá、担 dǎn、拉 là、拉 lǎ、拗 yào、拽 yè、指 zhí、指 zhī、挟 jiā、挡 dàng、捂 wú、据 jū、排 pǎi、掠 lüě、探 tān、掰 bò、掷 zhī、掺 chān、掺 càn、提 shí、揣 chuài、搅 jiǎ、摘 zhé、摩 mā、摸 mó、撞 chuáng、撩 liào、播 bò、撮 cuò、撮 cuǒ、擂 lēi、操 cào、敞 tǎng、散 san、敦 duì、文 wèn、斜 xiá、斤 jin、旁 bàng、无 mó、昔 xí、景 yǐng、暇 xià、暴 pù、曙 shù、曝 bào、有 yòu、期 qí、术 zhú、朴 piáo、朴 pú、杠 gāng、枕 zhèn、枝 qí、柄 bìng、柏 bò、查 zhā、栖 xī、框 kuāng、梢 sào、棱 líng、棱 lēng、棹 zhuō、椅 yī、椰 yé、楷 jiē、橙 chén、檐 yín、欠 qian、殖 shi、比 bì、氏 zhī、汞 hòng、沁 shèn、沈 chén、沓 ta、沙 shà、沮 jù、沮 jū、沿 yàn、泊 pò、泛 fán、波 pō、泣 xiè、洗 xiǎn、洽 xiá、浆 jiàng、浸 jīn、涌 chōng、涡 guō、液 yì、涸 hào、淆 yáo、淑 shú、混 hǔn、淹 yàn、渣 zhǎ、溃 huì、溪 qī、溺 niào、滑 gǔ、漆 qù、漆 xī、漫 mán、澎 pēng、瀑 bào、炊 chuì、炮 pāo、点 dian、烙 luò、烟 yīn、煽 shàn、熄 xí、熏 xùn、犬 quán、狡 jiǎ、率 shuò、玩 wàn、璃 li、甚 shé、甚 shén、疏 shù、癌 yán、百 bó、皎 jiǎ、皖 huǎn、盖 gě、盟 míng、盾 shǔn、瞧 yǎ、瞭 liǎo、知 zhì、矩 ju、矫 jiǎ、石 dàn、研 yàn、硅 huò、磅 pāng、祭 zhài、种 chóng、秘 lín、秤 chèn、秤 chēng、称 chèng、穴 xuè、究 jiù、突 tú、窘 jǔn、筑 zhú、箕 ji、粥 yù、紊 wèn、繁 pó、红 gōng、纪 jǐ、经 jìng、绕 rao、绕 rǎo、绞 jiǎ、绩 jī、绰 chuo、缩 sù、缴 jiǎ、罗 luo、罗 luō、罢 ba、署 shù、翕 xì、耀 yuè、肋 lè、肖 xiāo、育 yō、胜 shēng、胳 gā、脊 jí、脚 jiǎ、脚 jué、腋 yì、膀 bàng、膀 pāng、膊 bo、膜 mò、臂 bei、臂 bèi、舵 tuó、艘 sāo、色 shǎi、艾 yì、芒 wáng、芦 lǔ、芽 dí、若 rě、苹 pín、茬 zhā、茸 rǒng、荒 huang、莎 suō、莞 guān、莞 wān、萎 wēi、落 luō、落 lào、著 zhe、著 zhuó、著 zháo、著 zhāo、著 zhǔ、著 zī、蓝 la、蓝 lan、蔓 wàn、蔚 yù、薇 wéi、藓 lì、虫 huǐ、虹 jiàng、蚕 tiǎn、蛇 yí、蛾 yǐ、蜡 zhà、蜿 wǎn、蝎 hé、蟀 shuài、蟀 shuò、蟆 má、蠕 ruǎn、行 hàng、行 héng、行 xìng、衣 yì、衣 yǐ、衰 cuī、被 pī、褐 hé、见 xiàn、角 jiǎ、论 lún、识 shī、说 yuè、谁 shéi、谷 yù、豁 huá、赚 zuàn、趣 cù、足 jù、跄 qiāng、跌 dié、踉 liáng、踮 diē、身 juān、车 jū、转 zhuǎi、轴 zhòu、辑 ji、辟 pī、辱 rù、边 bian、过 guō、迹 jī、适 kuò、通 tòng、遂 suí、遍 piàn、遗 wèi、遮 zhe、那 nā、那 nǎ、郎 làng、鄙 bì、酪 luò、酵 xiào、酿 niàn、酿 niáng、采 cài、里 li、量 liang、铅 yán、锯 jū、镐 gǎo、镐 hào、阿 a、阿 à、阿 á、陆 liù、陶 yáo、隆 lōng、雌 cī、雪 xuè、革 jí、革 jǐ、鞠 jú、顿 dú、颈 gěng、饺 jiǎ、馨 xīng、驮 duò、骨 gú、魄 bó、魄 tuò、鸟 diǎo、麻 mā、鼓 hú、齐 jì、齐 qì
```
