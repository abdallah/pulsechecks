package provider

import (
	"context"
	"fmt"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/datasource/schema"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

var _ datasource.DataSource = &ChecksDataSource{}

func NewChecksDataSource() datasource.DataSource {
	return &ChecksDataSource{}
}

type ChecksDataSource struct {
	client *ApiClient
}

type ChecksDataSourceModel struct {
	TeamId types.String             `tfsdk:"team_id"`
	Checks []CheckDataSourceModel   `tfsdk:"checks"`
}

type CheckDataSourceModel struct {
	CheckId       types.String `tfsdk:"check_id"`
	Name          types.String `tfsdk:"name"`
	Status        types.String `tfsdk:"status"`
	PeriodSeconds types.Int64  `tfsdk:"period_seconds"`
	GraceSeconds  types.Int64  `tfsdk:"grace_seconds"`
	CreatedAt     types.String `tfsdk:"created_at"`
}

func (d *ChecksDataSource) Metadata(ctx context.Context, req datasource.MetadataRequest, resp *datasource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_checks"
}

func (d *ChecksDataSource) Schema(ctx context.Context, req datasource.SchemaRequest, resp *datasource.SchemaResponse) {
	resp.Schema = schema.Schema{
		MarkdownDescription: "Pulsechecks checks data source",

		Attributes: map[string]schema.Attribute{
			"team_id": schema.StringAttribute{
				MarkdownDescription: "Team identifier",
				Required:            true,
			},
			"checks": schema.ListNestedAttribute{
				MarkdownDescription: "List of checks",
				Computed:            true,
				NestedObject: schema.NestedAttributeObject{
					Attributes: map[string]schema.Attribute{
						"check_id": schema.StringAttribute{
							MarkdownDescription: "Check identifier",
							Computed:            true,
						},
						"name": schema.StringAttribute{
							MarkdownDescription: "Check name",
							Computed:            true,
						},
						"status": schema.StringAttribute{
							MarkdownDescription: "Check status",
							Computed:            true,
						},
						"period_seconds": schema.Int64Attribute{
							MarkdownDescription: "Check period in seconds",
							Computed:            true,
						},
						"grace_seconds": schema.Int64Attribute{
							MarkdownDescription: "Grace period in seconds",
							Computed:            true,
						},
						"created_at": schema.StringAttribute{
							MarkdownDescription: "Creation timestamp",
							Computed:            true,
						},
					},
				},
			},
		},
	}
}

func (d *ChecksDataSource) Configure(ctx context.Context, req datasource.ConfigureRequest, resp *datasource.ConfigureResponse) {
	if req.ProviderData == nil {
		return
	}

	client, ok := req.ProviderData.(*ApiClient)
	if !ok {
		resp.Diagnostics.AddError(
			"Unexpected Data Source Configure Type",
			fmt.Sprintf("Expected *ApiClient, got: %T", req.ProviderData),
		)
		return
	}

	d.client = client
}

func (d *ChecksDataSource) Read(ctx context.Context, req datasource.ReadRequest, resp *datasource.ReadResponse) {
	var data ChecksDataSourceModel

	resp.Diagnostics.Append(req.Config.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	// Note: This would need to be implemented in the API client
	// For now, we'll return an empty list
	data.Checks = []CheckDataSourceModel{}

	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}
