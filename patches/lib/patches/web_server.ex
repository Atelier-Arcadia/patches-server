defmodule Patches.WebServer do
  import Plug.Conn

  alias Patches.Timeout.Agent, as: Timeouts
  alias Patches.Server.Agent, as: Sessions
  alias Patches.StreamRegistry.Agent, as: VulnStreams

  @missing_params_msg "Request missing required query string parameters platform/requestID" 

  def init(options), do: options

  def call(conn, options), do: handle(conn, options)

  defp handle(conn, options) do
    query =
      conn
      |> Map.get(:query_string)
      |> Plug.Conn.Query.decode()

    case query do
      %{ "requestID" => req_id } ->
        serve_vulnerabilities(conn, req_id)

      %{ "platform" => platform } ->
        register_session(conn, platform)

      _ ->
        error(conn)
    end

    cleanup()
  end

  defp serve_vulnerabilities(conn, req_id) do
    Timeouts.notify_activity(session: req_id)

    {status, response} =
      case VulnStreams.retrieve(req_id) do
        [] ->
          {202, %{ "error" => "There are no vulnerabilities prepared for your session."}}

        vulns ->
          {200, %{ "error" => nil, "vulnerabilities" => vulns }}
      end

    body =
      Poison.encode!(response)

    send_resp(conn, status, body)
  end

  defp register_session(conn, platform) do
    {status, response} =
      case Sessions.queue_session(scanning: platform) do
        {:ok, new_session_id} ->
          Timeouts.notify_activity(session: new_session_id)

          {200, %{ "error" => nil, "requestID" => new_session_id }}

        {:error, :queue_full} ->
          {202, %{ "error" => "The server is too busy right now. Try again later." }}
      end

    body =
      Poison.encode!(response)

    send_resp(conn, status, body)
  end

  defp error(conn) do
    error =
      Poison.encode(%{ "Error" => @missing_params_msg })

    send_resp(conn, 400, error)
  end

  defp cleanup() do
    timed_out_sessions =
      Timeouts.timed_out()

    platforms_being_scanned =
      ServerAgent.active()
      |> Enum.map(&Map.get(&1, :platform))
      |> Enum.uniq()

    Enum.each(timed_out_sessions, fn session_id ->
      RegistryAgent.terminate_session(session_id)
      ServerAgent.terminate_session(session_id)
    end)

    Enum.each(platforms_being_scanned, fn platform ->
      if RegistryAgent.all_sessions_complete?(platform) do
        RegistryAgent.update_cache(platform)
      end
    end)
  end
end
