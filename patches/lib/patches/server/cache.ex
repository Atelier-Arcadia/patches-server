defmodule Patches.Server.Cache do
  @moduledoc """
  The cache is represented as a tree mapping platform names to a list of
  vulnerabilities affecting that platform.
  """
  
  @doc """
  Create a new empty cache state.
  """
  def init(platforms) do
    for pform <- platforms,
        into: %{},
        do: {pform, []}
  end

  @doc """
  Register a new vulnerability affecting a supported platform to the cache.
  """
  def register(cache, platform, vuln) do
    Map.update(cache, platform, [ vuln ], fn vulns -> [ vuln | vulns ] end)
  end

  @doc """
  Retrieve up to `limit` vulnerabilities affecting `platform` from an `offset`.
  """
  def retrieve(cache, platform, offset \\ 0, limit \\ 1) do
    Map.get(cache, platform, [])
    |> Enum.drop(offset)
    |> Enum.take(limit)
  end
end

defmodule Patches.Server.CacheAgent do
  @moduledoc """
  `Agent` abstraction for managing a cache.

  Vulnerabilities are, on average, less than 256 bytes.  The cache defaults
  to storing no more than 8000 vulnerabilities, which would occupy about
  2MB of space.

  ## Guarantees
  
  The cache guarantees that:

  1. It will never exceed an optional limit to the number of vulnerabilities
  in memory (default 8000).
  2. All iterations through a cache of vulnerabilities will be total. I.e.,
  all scanners will always get every vuln for their platform.
  """

  use Agent

  alias Patches.Server.Cache

  @doc """
  Start handling a cache state storing vulnerabilities for a list of platforms.
  """
  def start_link(platforms) do
    Agent.start_link(fn -> Cache.init(platforms) end)
  end
end
