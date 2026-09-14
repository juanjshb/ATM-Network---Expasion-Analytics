let
    Source = Sql.Database("localhost,1433", "atm_network"),
    Locations = Source{[Schema="dbo", Item="v_atm_locations_powerbi"]}[Data],
    Kpis = Source{[Schema="dbo", Item="v_atm_kpis_powerbi"]}[Data],
    Runs = Source{[Schema="dbo", Item="v_scrape_runs_powerbi"]}[Data]
in
    Locations

