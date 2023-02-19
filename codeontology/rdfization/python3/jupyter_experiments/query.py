import owlready2 as owl
from pyvis.network import Network


def list_query_results(query: str, max_res=20):
    max_line_len = 100
    n = len(str(max_res))

    results = [tuple(r) for r in owl.default_world.sparql(query)]
    results.sort(key=lambda x: x[0].iri if hasattr(x[0], "iri") else x[0])

    if results:
        print(f"Results:\n")
        for i, res in enumerate(results[:max_res], 1):
            i_str = str(i)
            tuple_iri_res = tuple([r.iri if hasattr(r, "iri") else str(r) for r in res])
            line_n = f"{' ' * (n - len(i_str))}{i_str}"
            to_print = f"{line_n} {tuple_iri_res}"
            if len(to_print) > max_line_len and len(tuple_iri_res) > 1:
                print(f"{' ' * (n - len(i_str))}{i_str} (")
                print("\n".join([f"{' ' * n}      {r}" for r in res]), end="\n,")
                print(f"{' ' * n} )")
            else:
                print(to_print)
        if max_res > 0 and len(results) > max_res:
            print(f"... {len(results) - max_res} more results ...")
    else:
        print(f"No results!")


def show_subgraph_from_entity(iri: str, ontology, w, h, max_deep=2, max_str_len=30):
    def get_id(e_):
        return e_.iri if hasattr(e_, "iri") else str(e_)

    def get_label(e_, role):
        maps = [("http://rdf.webofcode.org/woc/", "woc")]

        if getattr(e_, "label", []):
            str_e = e_.label[0]
        elif getattr(e_, "iri", ""):
            str_e = e_.iri
        else:
            str_e = str(e_)

        for m, mc in maps:
            str_e = str_e.replace(m, f"{mc}:")
        if len(str_e) > max_str_len:
            str_e = str_e[:max_str_len-3]+" ..."

        if role == 0:
            return f"{str_e}\n{type(e_).__name__}"
        elif role == 1:
            return str_e
        else:
            assert False

    def get_entities_and_triples(start_iri, deep):
        assert deep >= 0
        start_entity = list(ontology.search(iri=start_iri))[0]

        cumulated_entities = {(start_entity, type(start_entity),)}
        cumulated_triples = set()
        iris_complete = {start_iri}
        iris_by_deep = [{start_iri}]
        for i in range(deep):
            j = i+1
            iris_by_deep.append(set())
            for iri in list(iris_by_deep[i]):
                entity = list(ontology.search(iri=iri))[0]
                query = f"""
                prefix woc: <http://rdf.webofcode.org/woc/>

                SELECT DISTINCT ?s ?p ?o
                WHERE {{
                    {{<{iri}> ?p ?o}} UNION {{?s ?p <{iri}>}}
                }}
                """
                for triple in list(owl.default_world.sparql(query)):
                    assert len(triple) == 3

                    if isinstance(triple[1], int):
                        continue
                    for k in [0, 2]:
                        if triple[k] is None:
                            triple[k] = entity
                        if hasattr(triple[k], "iri") and not triple[k].iri in iris_complete:
                            iris_complete.add(triple[k].iri)
                            iris_by_deep[j].add(triple[k].iri)
                        cumulated_entities.add(
                            (triple[k], type(triple[k]),)
                        )
                    cumulated_triples.add((
                        (triple[0], type(triple[0]),),
                        triple[1],
                        (triple[2], type(triple[2]),),
                    ))

        return cumulated_entities, cumulated_triples

    entities, triples = get_entities_and_triples(iri, max_deep)

    net = Network(directed=True, width=f"{w}px", height=f"{h}px")
    for e, t_e in entities:
        net.add_node(get_id(e), label=get_label(e, 0), shape='circle')
    for ((subj, t_subj,), pred, (obj, t_obj,)) in triples:
        net.add_edge(get_id(subj), get_id(obj), label=get_label(pred, 1))
    net.repulsion(
        node_distance=200,
        central_gravity=0.2,
        spring_length=200,
        spring_strength=0.05,
        damping=0.09
    )
    net.set_edge_smooth('dynamic')
    save_name = f"subkg_from_{iri.split('/')[-1]}_deep{max_deep}.html"
    net.save_graph(save_name)
    return save_name
