package provider

import (
	"context"
	"fmt"

	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

var _ resource.Resource = &CheckResource{}

func NewCheckResource() resource.Resource {
	return &CheckResource{}
}

type CheckResource struct {
	client *ApiClient
}

type CheckResourceModel struct {
	CheckId       types.String `tfsdk:"check_id"`
	TeamId        types.String `tfsdk:"team_id"`
	Name          types.String `tfsdk:"name"`
	CheckType     types.String `tfsdk:"check_type"`
	PeriodSeconds types.Int64  `tfsdk:"period_seconds"`
	Schedule      types.String `tfsdk:"schedule"`
	GraceSeconds  types.Int64  `tfsdk:"grace_seconds"`
	Token         types.String `tfsdk:"token"`
	Status        types.String `tfsdk:"status"`
	CreatedAt     types.String `tfsdk:"created_at"`
}

func (r *CheckResource) Metadata(ctx context.Context, req resource.MetadataRequest, resp *resource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_check"
}

func (r *CheckResource) Schema(ctx context.Context, req resource.SchemaRequest, resp *resource.SchemaResponse) {
	resp.Schema = schema.Schema{
		MarkdownDescription: "Pulsechecks check resource. Use `check_type` to select the monitoring mode:\n- `heartbeat` — your service pings PulseChecks every `period_seconds`\n- `cron` — your cron job pings PulseChecks; next due time is derived from `schedule`\n- `http` — PulseChecks actively fetches a URL every `period_seconds`",

		Attributes: map[string]schema.Attribute{
			"check_id": schema.StringAttribute{
				MarkdownDescription: "Check identifier",
				Computed:            true,
			},
			"team_id": schema.StringAttribute{
				MarkdownDescription: "Team identifier",
				Required:            true,
			},
			"name": schema.StringAttribute{
				MarkdownDescription: "Check name",
				Required:            true,
			},
			"check_type": schema.StringAttribute{
				MarkdownDescription: "Check type: `heartbeat`, `cron`, or `http`",
				Required:            true,
			},
			"period_seconds": schema.Int64Attribute{
				MarkdownDescription: "Check period in seconds. Required for `heartbeat` and `http` types.",
				Optional:            true,
				Computed:            true,
			},
			"schedule": schema.StringAttribute{
				MarkdownDescription: "Cron expression (e.g. `0 2 * * *`). Required for `cron` type.",
				Optional:            true,
				Computed:            true,
			},
			"grace_seconds": schema.Int64Attribute{
				MarkdownDescription: "Grace period in seconds before alerting",
				Required:            true,
			},
			"token": schema.StringAttribute{
				MarkdownDescription: "Check ping token",
				Computed:            true,
				Sensitive:           true,
			},
			"status": schema.StringAttribute{
				MarkdownDescription: "Check status",
				Computed:            true,
			},
			"created_at": schema.StringAttribute{
				MarkdownDescription: "Creation timestamp",
				Computed:            true,
			},
		},
	}
}

func (r *CheckResource) Configure(ctx context.Context, req resource.ConfigureRequest, resp *resource.ConfigureResponse) {
	if req.ProviderData == nil {
		return
	}

	client, ok := req.ProviderData.(*ApiClient)
	if !ok {
		resp.Diagnostics.AddError(
			"Unexpected Resource Configure Type",
			fmt.Sprintf("Expected *ApiClient, got: %T", req.ProviderData),
		)
		return
	}

	r.client = client
}

func validateCheckModel(data CheckResourceModel, diags interface{ AddError(string, string) }) {
	checkType := data.CheckType.ValueString()
	switch checkType {
	case "cron":
		if data.Schedule.IsNull() || data.Schedule.IsUnknown() || data.Schedule.ValueString() == "" {
			diags.AddError("Missing schedule", "schedule is required when check_type is \"cron\"")
		}
	case "heartbeat", "http":
		if data.PeriodSeconds.IsNull() || data.PeriodSeconds.IsUnknown() || data.PeriodSeconds.ValueInt64() == 0 {
			diags.AddError("Missing period_seconds", fmt.Sprintf("period_seconds is required when check_type is %q", checkType))
		}
	default:
		diags.AddError("Invalid check_type", fmt.Sprintf("check_type must be one of: heartbeat, cron, http. Got: %q", checkType))
	}
}

func buildCheckRequest(data CheckResourceModel) CheckRequest {
	req := CheckRequest{
		Name:         data.Name.ValueString(),
		Type:         data.CheckType.ValueString(),
		GraceSeconds: int(data.GraceSeconds.ValueInt64()),
	}
	if !data.PeriodSeconds.IsNull() && !data.PeriodSeconds.IsUnknown() {
		req.PeriodSeconds = int(data.PeriodSeconds.ValueInt64())
	}
	if !data.Schedule.IsNull() && !data.Schedule.IsUnknown() {
		req.Schedule = data.Schedule.ValueString()
	}
	return req
}

func applyCheckToModel(check *Check, data *CheckResourceModel) {
	data.CheckId = types.StringValue(check.CheckId)
	data.Name = types.StringValue(check.Name)
	data.CheckType = types.StringValue(check.CheckType)
	data.GraceSeconds = types.Int64Value(int64(check.GraceSeconds))
	data.Token = types.StringValue(check.Token)
	data.Status = types.StringValue(check.Status)
	data.CreatedAt = types.StringValue(check.CreatedAt)
	if check.PeriodSeconds != 0 {
		data.PeriodSeconds = types.Int64Value(int64(check.PeriodSeconds))
	}
	if check.Schedule != "" {
		data.Schedule = types.StringValue(check.Schedule)
	}
}

func (r *CheckResource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {
	var data CheckResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	validateCheckModel(data, &resp.Diagnostics)
	if resp.Diagnostics.HasError() {
		return
	}

	check, err := r.client.CreateCheck(data.TeamId.ValueString(), buildCheckRequest(data))
	if err != nil {
		resp.Diagnostics.AddError("Client Error", fmt.Sprintf("Unable to create check: %s", err))
		return
	}

	applyCheckToModel(check, &data)
	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *CheckResource) Read(ctx context.Context, req resource.ReadRequest, resp *resource.ReadResponse) {
	var data CheckResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	check, err := r.client.GetCheck(data.TeamId.ValueString(), data.CheckId.ValueString())
	if err != nil {
		resp.Diagnostics.AddError("Client Error", fmt.Sprintf("Unable to read check: %s", err))
		return
	}

	if check == nil {
		resp.State.RemoveResource(ctx)
		return
	}

	applyCheckToModel(check, &data)
	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *CheckResource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {
	var data CheckResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	validateCheckModel(data, &resp.Diagnostics)
	if resp.Diagnostics.HasError() {
		return
	}

	check, err := r.client.UpdateCheck(data.TeamId.ValueString(), data.CheckId.ValueString(), buildCheckRequest(data))
	if err != nil {
		resp.Diagnostics.AddError("Client Error", fmt.Sprintf("Unable to update check: %s", err))
		return
	}

	applyCheckToModel(check, &data)
	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *CheckResource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) {
	var data CheckResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	if err := r.client.DeleteCheck(data.TeamId.ValueString(), data.CheckId.ValueString()); err != nil {
		resp.Diagnostics.AddError("Client Error", fmt.Sprintf("Unable to delete check: %s", err))
	}
}
