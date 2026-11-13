import { gql } from "graphql-tag";

export const typeDefs = gql`
  type Product {
    id: ID!
    title: String!
    price: Float!
    vendor: String
  }

  type Query {
    products(first: Int = 20, after: ID): [Product!]!
    product(id: ID!): Product
  }

  type Mutation {
    createProduct(title: String!, price: Float!): Product!
  }
`;

export const resolvers = {
  Query: {
    products: (_: unknown, args: { first: number }, ctx: any) => ctx.db.products.list(args.first),
    product: (_: unknown, args: { id: string }, ctx: any) => ctx.loaders.productById.load(args.id),
  },
  Mutation: {
    createProduct: (_: unknown, args: any, ctx: any) => ctx.db.products.insert(args),
  },
};
