package provider

import (
	"context"
	"net/http"
	"os"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/provider"
	"github.com/hashicorp/terraform-plugin-framework/provider/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

var _ provider.Provider = &pulsechecksProvider{}

type pulsechecksProvider struct {
	version string
}

type pulsechecksProviderModel struct {
	ApiUrl types.String `tfsdk:"api_url"`
	Token  types.String `tfsdk:"token"`
}

func (p *pulsechecksProvider) Metadata(ctx context.Context, req provider.MetadataRequest, resp *provider.MetadataResponse) {
	resp.TypeName = "pulsechecks"
	resp.Version = p.version
}

func (p *pulsechecksProvider) Schema(ctx context.Context, req provider.SchemaRequest, resp *provider.SchemaResponse) {
	resp.Schema = schema.Schema{
		Attributes: map[string]schema.Attribute{
			"api_url": schema.StringAttribute{
				MarkdownDescription: "Pulsechecks API URL",
				Optional:            true,
			},
			"token": schema.StringAttribute{
				MarkdownDescription: "API authentication token",
				Optional:            true,
				Sensitive:           true,
			},
		},
	}
}

func (p *pulsechecksProvider) Configure(ctx context.Context, req provider.ConfigureRequest, resp *provider.ConfigureResponse) {
	var data pulsechecksProviderModel

	resp.Diagnostics.Append(req.Config.Get(ctx, &data)...)

	if resp.Diagnostics.HasError() {
		return
	}

	apiUrl := os.Getenv("PULSECHECKS_API_URL")
	if !data.ApiUrl.IsNull() {
		apiUrl = data.ApiUrl.ValueString()
	}

	token := os.Getenv("PULSECHECKS_TOKEN")
	if !data.Token.IsNull() {
		token = data.Token.ValueString()
	}

	if apiUrl == "" {
		resp.Diagnostics.AddError(
			"Unable to find API URL",
			"API URL cannot be an empty string",
		)
		return
	}

	client := &http.Client{}
	apiClient := &ApiClient{
		BaseURL:    apiUrl,
		Token:      token,
		HTTPClient: client,
	}

	resp.DataSourceData = apiClient
	resp.ResourceData = apiClient
}

func (p *pulsechecksProvider) Resources(ctx context.Context) []func() resource.Resource {
	return []func() resource.Resource{
		NewTeamResource,
		NewCheckResource,
	}
}

func (p *pulsechecksProvider) DataSources(ctx context.Context) []func() datasource.DataSource {
	return []func() datasource.DataSource{
		NewTeamDataSource,
		NewChecksDataSource,
	}
}

func New(version string) func() provider.Provider {
	return func() provider.Provider {
		return &pulsechecksProvider{
			version: version,
		}
	}
}
