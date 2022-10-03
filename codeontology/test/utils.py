import owlready2 as owl


def do_query_and_show_res(query: str, max_res=20) -> list:
    MAX_LINE_LEN = 125

    n = len(str(max_res))
    results = [tuple(r) for r in owl.default_world.sparql(query)]
    shown_res = []
    if results:
        print(f"Results:\n")
        for i, res in enumerate(results[:max_res], 1) if max_res > 0 else enumerate(results, 1):
            i_str = str(i)
            # for r in res:
            #     if type(r) is str:
            #         print(f"WARN {r}")
            new_res = []
            for r in res:
                try:
                    to_append = r.iri
                except:
                    to_append = str(r)
                new_res.append(to_append)
            new_res = tuple(new_res)
            to_print = f"{' ' * (n - len(i_str))}{i_str} {new_res}"
            if len(to_print) > MAX_LINE_LEN and len(new_res) > 1:
                print(f"{' ' * (n - len(i_str))}{i_str} (")
                for r in new_res[:-1]:
                    print(f"{' ' * n}      {r}")
                print(f"{' ' * n}      {new_res[-1]},")
                print(f"{' ' * n} )")
            else:
                print(to_print)
            shown_res.append(res)
        if max_res > 0 and len(results) > max_res:
            print(f"... {len(results) - max_res} more results ...")
    else:
        print(f"No results!")
    return shown_res
