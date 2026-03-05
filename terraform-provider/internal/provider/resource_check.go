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
	PeriodSeconds types.Int64  `tfsdk:"period_seconds"`
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
		MarkdownDescription: "Pulsechecks check resource",

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
			"period_seconds": schema.Int64Attribute{
				MarkdownDescription: "Check period in seconds",
				Required:            true,
			},
			"grace_seconds": schema.Int64Attribute{
				MarkdownDescription: "Grace period in seconds",
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

func (r *CheckResource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {
	var data CheckResourceModel

	resp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	check, err := r.client.CreateCheck(
		data.TeamId.ValueString(),
		data.Name.ValueString(),
		int(data.PeriodSeconds.ValueInt64()),
		int(data.GraceSeconds.ValueInt64()),
	)
	if err != nil {
		resp.Diagnostics.AddError("Client Error", fmt.Sprintf("Unable to create check, got error: %s", err))
		return
	}

	data.CheckId = types.StringValue(check.CheckId)
	data.Token = types.StringValue(check.Token)
	data.Status = types.StringValue(check.Status)
	data.CreatedAt = types.StringValue(check.CreatedAt)

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
		resp.Diagnostics.AddError("Client Error", fmt.Sprintf("Unable to read check, got error: %s", err))
		return
	}

	if check == nil {
		resp.State.RemoveResource(ctx)
		return
	}

	data.Name = types.StringValue(check.Name)
	data.PeriodSeconds = types.Int64Value(int64(check.PeriodSeconds))
	data.GraceSeconds = types.Int64Value(int64(check.GraceSeconds))
	data.Token = types.StringValue(check.Token)
	data.Status = types.StringValue(check.Status)
	data.CreatedAt = types.StringValue(check.CreatedAt)

	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *CheckResource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {
	var data CheckResourceModel

	resp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	check, err := r.client.UpdateCheck(
		data.TeamId.ValueString(),
		data.CheckId.ValueString(),
		data.Name.ValueString(),
		int(data.PeriodSeconds.ValueInt64()),
		int(data.GraceSeconds.ValueInt64()),
	)
	if err != nil {
		resp.Diagnostics.AddError("Client Error", fmt.Sprintf("Unable to update check, got error: %s", err))
		return
	}

	data.Name = types.StringValue(check.Name)
	data.PeriodSeconds = types.Int64Value(int64(check.PeriodSeconds))
	data.GraceSeconds = types.Int64Value(int64(check.GraceSeconds))
	data.Token = types.StringValue(check.Token)
	data.Status = types.StringValue(check.Status)

	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *CheckResource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) {
	var data CheckResourceModel

	resp.Diagnostics.Append(req.State.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	err := r.client.DeleteCheck(data.TeamId.ValueString(), data.CheckId.ValueString())
	if err != nil {
		resp.Diagnostics.AddError("Client Error", fmt.Sprintf("Unable to delete check, got error: %s", err))
		return
	}
}
