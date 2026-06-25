from collections import defaultdict

from invistigator.schemas import GraphData, GraphEdge, GraphNode, ProfileData


def _attributes(profile: ProfileData) -> list[tuple[str, str, str]]:
    """Возвращает (kind, value, label) атрибутов аккаунта для рёбер графа."""
    o = profile.osint
    items: list[tuple[str, str, str]] = []
    # telegram-каналы живут на самом ProfileData
    for tg in profile.telegram_links:
        items.append(("telegram", tg, tg))
    if o is None:
        return items
    if o.domain:
        items.append(("domain", o.domain, o.domain))
    for ph in o.phones:
        items.append(("phone", ph, ph))
    for em in o.emails:
        items.append(("email", em, em))
    for w in o.crypto_wallets:
        items.append(("wallet", w, w))
    for s in o.other_socials:
        items.append(("social", s, s))
    if o.avatar_phash:
        items.append(("avatar", o.avatar_phash, f"avatar:{o.avatar_phash[:8]}"))
    return items


def build_graph(profiles: list[ProfileData], min_shared: int = 2) -> GraphData:
    """Бипартитный граф: account ↔ attribute. Атрибуты с <min_shared аккаунтов отсеиваются."""
    # attr_id -> множество account_id, привязанных к нему
    attr_accounts: dict[str, set[str]] = defaultdict(set)
    attr_meta: dict[str, tuple[str, str]] = {}  # attr_id -> (type, label)
    account_nodes: dict[str, GraphNode] = {}

    for p in profiles:
        acc_id = f"account:{p.username}"
        account_nodes[acc_id] = GraphNode(
            id=acc_id, type="account", label=p.username,
            data={"followers": p.followers, "status": p.status},
        )
        for kind, value, label in _attributes(p):
            attr_id = f"{kind}:{value}"
            attr_accounts[attr_id].add(acc_id)
            attr_meta[attr_id] = (kind, label)

    nodes: list[GraphNode] = list(account_nodes.values())
    edges: list[GraphEdge] = []
    for attr_id, accs in attr_accounts.items():
        if len(accs) < min_shared:
            continue
        kind, label = attr_meta[attr_id]
        nodes.append(GraphNode(id=attr_id, type=kind, label=label))
        for acc_id in sorted(accs):
            edges.append(GraphEdge(source=acc_id, target=attr_id, kind=kind))

    return GraphData(nodes=nodes, edges=edges)
